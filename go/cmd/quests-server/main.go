package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/valirum/quests/go/internal/config"
	"github.com/valirum/quests/go/internal/db"
	"github.com/valirum/quests/go/internal/events"
	"github.com/valirum/quests/go/internal/health"
	"github.com/valirum/quests/go/internal/httpapi"
	"github.com/valirum/quests/go/internal/schedule"
	"github.com/valirum/quests/go/internal/store"
)

func main() {
	cfg := config.Load()

	sqlDB, err := db.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("db: %v", err)
	}
	defer sqlDB.Close()

	hub := events.New()
	st := &store.Store{DB: sqlDB}
	srv := &httpapi.Server{
		Store:   st,
		Health:  health.New(),
		Hub:     hub,
		CORS:    cfg.CORS,
		DataDir: cfg.DataDir,
		Root:    cfg.Root,
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

	log.Printf("quests-server (go) listening on http://%s  db=%s", addr, cfg.DBPath)
	if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}

func strPtr(s string) *string { return &s }
