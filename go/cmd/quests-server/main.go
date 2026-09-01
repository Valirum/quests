package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/valirum/quests/go/internal/auth"
	"github.com/valirum/quests/go/internal/config"
	"github.com/valirum/quests/go/internal/db"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/health"
	"github.com/valirum/quests/go/internal/httpapi"
	"github.com/valirum/quests/go/internal/schedule"
	"github.com/valirum/quests/go/internal/store"
)

func main() {
	if runAdmin(os.Args[1:]) {
		return
	}

	config.LoadDotenv(config.Load().Root)
	cfg := config.Load()

	sqlDB, err := db.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("db: %v", err)
	}
	defer sqlDB.Close()

	authStore := &auth.Store{DB: sqlDB}
	userCount, err := authStore.CountUsers()
	if err != nil {
		log.Fatalf("auth: %v", err)
	}

	authRequired := userCount > 0
	switch cfg.AuthMode {
	case "on":
		authRequired = true
	case "off":
		authRequired = false
	}
	if authRequired && userCount == 0 {
		log.Fatal("QUESTS_AUTH=on but no accounts exist; create one: quests-server useradd <username>")
	}
	// Refuse to expose an unauthenticated instance beyond loopback — the whole
	// point of accounts is that this cannot happen by forgetting a step.
	if !authRequired && !cfg.IsLoopbackBind() {
		log.Fatalf("refusing to bind %s with authentication disabled.\n"+
			"Create an account first:  quests-server useradd <username>\n"+
			"(or set QUESTS_AUTH=off deliberately for a trusted private network)", cfg.Addr())
	}

	internalToken, _, err := auth.NewToken()
	if err != nil {
		log.Fatalf("auth: %v", err)
	}

	hub := events.New()
	st := &store.Store{DB: sqlDB}
	srv := &httpapi.Server{
		Store:         st,
		Auth:          authStore,
		AuthRequired:  authRequired,
		SecureCookies: cfg.SecureCookies,
		InternalToken: internalToken,
		Health:        health.New(),
		Hub:           hub,
		CORS:          cfg.CORS,
		DataDir:       cfg.DataDir,
		Root:          cfg.Root,
		SelfBase:      fmt.Sprintf("http://127.0.0.1:%d", cfg.Port),
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	windows := schedule.NewWindowNotifier()
	go schedule.RunMaintenanceLoop(ctx, st, hub, windows)

	hub.Publish("startup", events.PublishOpts{
		Title:  "Quests",
		Detail: "server ready",
		Toast:  false,
		Source: "system",
		Sound:  strPtr(""),
	})

	addr := cfg.Addr()
	httpSrv := &http.Server{Addr: addr, Handler: srv.Handler()}
	go func() {
		<-ctx.Done()
		_ = httpSrv.Shutdown(context.Background())
	}()

	authNote := "auth=on"
	if !authRequired {
		authNote = "auth=OFF (loopback only)"
	}
	log.Printf("quests-server (go) listening on http://%s  db=%s  %s", addr, cfg.DBPath, authNote)
	if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func strPtr(s string) *string { return &s }
