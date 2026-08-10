package httpapi

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

func (s *Server) mountSPA(mux *http.ServeMux) {
	dist := filepath.Join(s.Root, "frontend", "dist")
	if st, err := os.Stat(dist); err != nil || !st.IsDir() {
		return
	}
	assets := filepath.Join(dist, "assets")
	if st, err := os.Stat(assets); err == nil && st.IsDir() {
		mux.Handle("GET /assets/", http.StripPrefix("/assets/", http.FileServer(http.Dir(assets))))
	}
	index := filepath.Join(dist, "index.html")
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, index)
	})
	mux.HandleFunc("GET /{path...}", func(w http.ResponseWriter, r *http.Request) {
		p := r.PathValue("path")
		if p == "" || strings.HasPrefix(p, "api/") || p == "api" || p == "ws" ||
			p == "docs" || p == "openapi.json" || p == "redoc" {
			http.NotFound(w, r)
			return
		}
		candidate := filepath.Join(dist, filepath.Clean("/"+p))
		if !strings.HasPrefix(candidate, dist) {
			http.NotFound(w, r)
			return
		}
		if st, err := os.Stat(candidate); err == nil && !st.IsDir() {
			http.ServeFile(w, r, candidate)
			return
		}
		http.ServeFile(w, r, index)
	})
}
