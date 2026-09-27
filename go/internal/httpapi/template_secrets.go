package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"regexp"
	"strconv"

	"github.com/valirum/quests/go/internal/store"
)

// secretKeyPattern matches a valid env var name — secrets are injected into
// the emit_pool_command child process verbatim as NAME=value (see
// schedule.execEmitPoolCommand), so the name has to be one.
var secretKeyPattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]*$`)

// listTemplateSecrets returns only the configured secret *names* — the
// values never come back from a read endpoint (or, by extension, MCP's
// list_templates/get_template), only from ResolveTemplateSecrets at exec
// time. See note=14.
func (s *Server) listTemplateSecrets(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if _, err := s.Store.GetTemplate(r.Context(), id); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Template not found")
			return
		}
		writeErr(w, 500, err.Error())
		return
	}
	keys, err := s.Store.ListTemplateSecretKeys(r.Context(), id)
	if err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	writeJSON(w, 200, map[string]any{"keys": keys})
}

// putTemplateSecret writes one secret value — write-only, the request body
// is never echoed back and no GET on this resource returns it.
func (s *Server) putTemplateSecret(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	key := r.PathValue("key")
	if !secretKeyPattern.MatchString(key) {
		writeErr(w, 422, "key must look like an env var name: [A-Za-z_][A-Za-z0-9_]*")
		return
	}
	var body struct {
		Value string `json:"value"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, 400, "invalid JSON")
		return
	}
	if body.Value == "" {
		writeErr(w, 422, "value required (use DELETE to remove a secret)")
		return
	}
	if _, err := s.Store.GetTemplate(r.Context(), id); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, 404, "Template not found")
			return
		}
		writeErr(w, 500, err.Error())
		return
	}
	if err := s.Store.SetTemplateSecret(r.Context(), id, key, body.Value); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	w.WriteHeader(204)
}

func (s *Server) deleteTemplateSecret(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	key := r.PathValue("key")
	if err := s.Store.DeleteTemplateSecret(r.Context(), id, key); err != nil {
		writeErr(w, 500, err.Error())
		return
	}
	w.WriteHeader(204)
}
