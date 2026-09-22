package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/google/uuid"
)

// maxPDFHTMLBytes caps the HTML payload accepted for rendering — generous
// for a note/quest export, small enough to bound weasyprint's memory/time.
const maxPDFHTMLBytes = 20 << 20 // 20MB

func (s *Server) registerPDF(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/export/pdf", s.postRenderPDF)
}

type renderPDFRequest struct {
	HTML     string `json:"html"`
	Filename string `json:"filename"`
}

// postRenderPDF converts a self-contained HTML document (inline CSS, no
// external assets) to PDF via WeasyPrint — a real HTML+CSS layout/paginator,
// not a screenshot: text stays selectable, @page/break-inside rules drive
// margins and pagination instead of hand-rolled pixel math.
func (s *Server) postRenderPDF(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, maxPDFHTMLBytes)
	var req renderPDFRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid JSON or HTML too large")
		return
	}
	if req.HTML == "" {
		writeErr(w, http.StatusBadRequest, "html is required")
		return
	}

	workDir, err := os.MkdirTemp("", "quests-pdf-*")
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer os.RemoveAll(workDir)

	inPath := filepath.Join(workDir, "in.html")
	outPath := filepath.Join(workDir, "out.pdf")
	if err := os.WriteFile(inPath, []byte(req.HTML), 0o644); err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "weasyprint", inPath, outPath)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		writeErr(w, http.StatusInternalServerError, "pdf render failed: "+stderr.String())
		return
	}

	pdf, err := os.ReadFile(outPath)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}

	filename := req.Filename
	if filename == "" {
		filename = uuid.NewString() + ".pdf"
	}
	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", `attachment; filename="`+sanitizeFilename(filename)+`"`)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(pdf)
}

func sanitizeFilename(name string) string {
	out := make([]rune, 0, len(name))
	for _, r := range name {
		if r == '"' || r == '\\' || r == '\n' || r == '\r' {
			continue
		}
		out = append(out, r)
	}
	if len(out) == 0 {
		return "export.pdf"
	}
	return string(out)
}
