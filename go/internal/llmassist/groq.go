package llmassist

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

type Settings struct {
	Provider    string
	APIKey      string
	Model       string
	BaseURL     string
	Timeout     time.Duration
	Temperature float64
	Proxy       string
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func envFloat(key string, def float64) float64 {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return def
	}
	if v, err := strconv.ParseFloat(raw, 64); err == nil {
		return v
	}
	return def
}

// LoadSettings mirrors Python's quests.llm.config.load_llm_settings for the
// groq provider (the only one the action-batch assistant supports).
func LoadSettings() Settings {
	model := strings.TrimSpace(os.Getenv("QUESTS_LLM_MODEL"))
	if model == "" {
		model = "openai/gpt-oss-20b"
	}
	base := strings.TrimSpace(os.Getenv("QUESTS_LLM_BASE"))
	if base == "" {
		base = "https://api.groq.com/openai/v1"
	}
	return Settings{
		Provider:    "groq",
		APIKey:      firstNonEmpty(os.Getenv("QUESTS_GROQ_API_KEY"), os.Getenv("GROQ_API_KEY")),
		Model:       model,
		BaseURL:     strings.TrimRight(base, "/"),
		Timeout:     time.Duration(envFloat("QUESTS_LLM_TIMEOUT", 180) * float64(time.Second)),
		Temperature: envFloat("QUESTS_LLM_TEMPERATURE", 0.1),
		Proxy:       firstNonEmpty(os.Getenv("QUESTS_LLM_PROXY"), os.Getenv("QUESTS_TG_PROXY")),
	}
}

type LLMError struct{ msg string }

func (e *LLMError) Error() string { return e.msg }
func llmErrf(format string, a ...any) error {
	return &LLMError{msg: fmt.Sprintf(format, a...)}
}

// ExtractActionBatch calls Groq with constrained JSON-schema decoding and
// parses the result into an ActionBatch. No agentic tool-calling loop —
// one request, one structured answer, same as the quest-draft path.
func ExtractActionBatch(ctx context.Context, settings Settings, text string) (ActionBatch, error) {
	if settings.Provider != "groq" {
		return ActionBatch{}, llmErrf("action-batch извлечение поддерживается только через Groq (provider=%q)", settings.Provider)
	}
	if settings.APIKey == "" {
		return ActionBatch{}, llmErrf("нужен GROQ_API_KEY или QUESTS_GROQ_API_KEY (console.groq.com → API Keys)")
	}

	payload := map[string]any{
		"model": settings.Model,
		"messages": []map[string]string{
			{"role": "system", "content": SystemPrompt()},
			{"role": "user", "content": strings.TrimSpace(text)},
		},
		"temperature": settings.Temperature,
		"response_format": map[string]any{
			"type": "json_schema",
			"json_schema": map[string]any{
				"name":   "action_batch",
				"schema": ActionBatchJSONSchema(),
			},
		},
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return ActionBatch{}, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, settings.BaseURL+"/chat/completions", bytes.NewReader(body))
	if err != nil {
		return ActionBatch{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Authorization", "Bearer "+settings.APIKey)
	// Cloudflare in front of api.groq.com bans the default Go User-Agent in
	// some regions, same reason the old Python client set this.
	req.Header.Set("User-Agent", "quests-bot/1.0")

	client := &http.Client{Timeout: settings.Timeout}
	if settings.Proxy != "" {
		proxyURL, perr := url.Parse(settings.Proxy)
		if perr == nil {
			client.Transport = &http.Transport{Proxy: http.ProxyURL(proxyURL)}
		}
	}

	resp, err := client.Do(req)
	if err != nil {
		return ActionBatch{}, llmErrf("не удалось связаться с Groq: %v", err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return ActionBatch{}, err
	}
	if resp.StatusCode >= 400 {
		detail := string(raw)
		if len(detail) > 400 {
			detail = detail[:400]
		}
		return ActionBatch{}, llmErrf("Groq HTTP %d: %s", resp.StatusCode, detail)
	}

	var parsed struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(raw, &parsed); err != nil || len(parsed.Choices) == 0 {
		return ActionBatch{}, llmErrf("пустой ответ Groq: %s", truncate(string(raw), 300))
	}
	return parseActionBatch(parsed.Choices[0].Message.Content)
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

// parseActionBatch recovers JSON that models sometimes wrap in prose or
// markdown fences, same fallback the Python parser used.
func parseActionBatch(raw string) (ActionBatch, error) {
	text := strings.TrimSpace(raw)
	if strings.HasPrefix(text, "```") {
		text = strings.Trim(text, "`")
		if strings.HasPrefix(strings.ToLower(text), "json") {
			text = strings.TrimSpace(text[4:])
		}
	}
	if !strings.HasPrefix(text, "{") {
		start := strings.Index(text, "{")
		end := strings.LastIndex(text, "}")
		if start >= 0 && end > start {
			text = text[start : end+1]
		}
	}
	var batch ActionBatch
	if err := json.Unmarshal([]byte(text), &batch); err != nil {
		return ActionBatch{}, llmErrf("модель вернула не-JSON: %v", err)
	}
	return batch, nil
}
