package llmassist

import (
	"strings"
	"testing"
)

func TestSystemPromptForbidsClarifyingOnlyAfterAnAnswer(t *testing.T) {
	pc := DefaultPromptContext(nil)
	if strings.Contains(SystemPrompt(pc), "УТОЧНЯТЬ БОЛЬШЕ НЕЛЬЗЯ") {
		t.Fatal("the first request may still ask a question")
	}
	pc.NoClarify = true
	if !strings.Contains(SystemPrompt(pc), "УТОЧНЯТЬ БОЛЬШЕ НЕЛЬЗЯ") {
		t.Fatal("after an answer the prompt must forbid another question")
	}
}
