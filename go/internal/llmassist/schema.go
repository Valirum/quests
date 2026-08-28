// Package llmassist is the Go port of the action-batch assistant: free text
// -> Groq structured JSON batch of quest actions -> dry-run preview -> apply.
// Same non-agentic philosophy as before (constrained decode, no tool-calling
// loop) — this package used to be a standalone Python aiohttp service
// (quests-llm); it's now in-process with the main API since Go has no heavy
// per-language dependency cost to isolate.
package llmassist

import "encoding/json"

var actionKinds = []string{
	"create_questline",
	"create_quest",
	"add_step",
	"update_step",
	"delete_step",
	"update_quest",
}

var statusValues = []string{"active", "delayed", "completed", "failed", "archived"}

// ActionStep is an inline step for create_quest's steps list.
type ActionStep struct {
	Title           string `json:"title"`
	Description     string `json:"description"`
	ProgressTotal   int    `json:"progress_total"`
	ProgressCurrent int    `json:"progress_current"`
}

// Action mirrors the flat action shape from the (former) Python schema —
// one struct covers all six action kinds, unused fields stay null.
type Action struct {
	Index  int    `json:"index"`
	Action string `json:"action"`

	Title           *string `json:"title"`
	Description     *string `json:"description"`
	Status          *string `json:"status"`
	Significance    *string `json:"significance"`
	Pinned          *bool   `json:"pinned"`
	SortOrder       *int    `json:"sort_order"`
	DeadlineAt      *string `json:"deadline_at"`
	DurationSeconds *int    `json:"duration_seconds"`

	Category       *string `json:"category"`
	CategoryID     *int64  `json:"category_id"`
	Questline      *string `json:"questline"`
	QuestlineID    *int64  `json:"questline_id"`
	ClearQuestline bool    `json:"clear_questline"`
	Color          *string `json:"color"`
	Icon           *string `json:"icon"`

	QuestID         *int64       `json:"quest_id"`
	StepID          *int64       `json:"step_id"`
	ProgressCurrent *int         `json:"progress_current"`
	ProgressTotal   *int         `json:"progress_total"`
	Steps           []ActionStep `json:"steps"`

	QuestlineIDRef *int `json:"questline_id_ref"`
	QuestIDRef     *int `json:"quest_id_ref"`
}

type ActionBatch struct {
	NeedsClarification bool     `json:"needs_clarification"`
	ClarifyQuestion    string   `json:"clarify_question"`
	Actions            []Action `json:"actions"`
}

func actionJSONSchema() map[string]any {
	strOrNull := map[string]any{"anyOf": []any{map[string]any{"type": "string"}, map[string]any{"type": "null"}}}
	intOrNull := map[string]any{"anyOf": []any{map[string]any{"type": "integer"}, map[string]any{"type": "null"}}}
	boolOrNull := map[string]any{"anyOf": []any{map[string]any{"type": "boolean"}, map[string]any{"type": "null"}}}
	strMax := func(max int) map[string]any {
		return map[string]any{"anyOf": []any{map[string]any{"type": "string", "maxLength": max}, map[string]any{"type": "null"}}}
	}
	return map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"properties": map[string]any{
			"index":            map[string]any{"type": "integer", "minimum": 0},
			"action":           map[string]any{"type": "string", "enum": actionKinds},
			"title":            strMax(200),
			"description":      strOrNull,
			"status":           map[string]any{"anyOf": []any{map[string]any{"type": "string", "enum": statusValues}, map[string]any{"type": "null"}}},
			"significance":     strOrNull,
			"pinned":           boolOrNull,
			"sort_order":       intOrNull,
			"deadline_at":      strOrNull,
			"duration_seconds": intOrNull,
			"category":         strOrNull,
			"category_id":      intOrNull,
			"questline":        strOrNull,
			"questline_id":     intOrNull,
			"clear_questline":  map[string]any{"type": "boolean"},
			"color":            strOrNull,
			"icon":             strOrNull,
			"quest_id":         intOrNull,
			"step_id":          intOrNull,
			"progress_current": intOrNull,
			"progress_total":   intOrNull,
			"steps": map[string]any{
				"anyOf": []any{
					map[string]any{
						"type": "array",
						"items": map[string]any{
							"type":                 "object",
							"additionalProperties": false,
							"properties": map[string]any{
								"title":            map[string]any{"type": "string", "minLength": 1, "maxLength": 200},
								"description":      map[string]any{"type": "string"},
								"progress_total":   map[string]any{"type": "integer", "minimum": 1},
								"progress_current": map[string]any{"type": "integer", "minimum": 0},
							},
							"required": []any{"title", "description", "progress_total", "progress_current"},
						},
						"maxItems": 20,
					},
					map[string]any{"type": "null"},
				},
			},
			"questline_id_ref": intOrNull,
			"quest_id_ref":     intOrNull,
		},
		"required": []any{
			"index", "action", "title", "description", "status", "significance",
			"pinned", "sort_order", "deadline_at", "duration_seconds",
			"category", "category_id", "questline", "questline_id",
			"clear_questline", "color", "icon", "quest_id", "step_id",
			"progress_current", "progress_total", "steps",
			"questline_id_ref", "quest_id_ref",
		},
	}
}

// ActionBatchJSONSchema is the response_format.json_schema.schema sent to Groq.
func ActionBatchJSONSchema() map[string]any {
	return map[string]any{
		"type":                 "object",
		"additionalProperties": false,
		"properties": map[string]any{
			"needs_clarification": map[string]any{"type": "boolean"},
			"clarify_question":    map[string]any{"type": "string"},
			"actions": map[string]any{
				"type":     "array",
				"items":    actionJSONSchema(),
				"maxItems": 20,
			},
		},
		"required": []any{"needs_clarification", "clarify_question", "actions"},
	}
}

// SystemPrompt is the same Russian prompt the Python version used, verbatim.
func SystemPrompt() string {
	schema, _ := json.Marshal(ActionBatchJSONSchema())
	return "Ты преобразуешь запрос пользователя в список действий (actions) над " +
		"журналом квестов Quests.\n" +
		"СИНТАКСИС ССЫЛОК: quest=N / questline=N / step=N — это точные числовые id, " +
		"подставленные фронтом через автокомплит по УЖЕ СУЩЕСТВУЮЩЕЙ сущности. " +
		"Если видишь такой тег — просто скопируй N в соответствующее *_id поле, " +
		"ничего не резолвь и не выдумывай.\n" +
		"Любое название БЕЗ такого тега (обычный текст) — это title НОВОЙ сущности, " +
		"которую нужно создать (create_quest/create_questline/новый шаг). " +
		"Если голый текст совпадает с title, который создаётся ДРУГИМ action'ом в " +
		"ЭТОМ ЖЕ списке — это ссылка на него: используй questline_id_ref/quest_id_ref " +
		"с индексом создающего action'а, а НЕ questline_id/quest_id и НЕ " +
		"questline/category (те поля — только для имени НОВОГО объекта при его " +
		"создании или для резолва имени уже существующего объекта по подстроке).\n" +
		"Действия и когда их использовать:\n" +
		"  • create_questline — создать новый квестлайн. title обязателен.\n" +
		"  • create_quest — создать НОВЫЙ квест с нуля. steps — только если " +
		"пользователь явно перечислил шаги нового квеста. Если квест создаётся " +
		"СРАЗУ ВНУТРИ квестлайна, который тоже создаётся в этом же запросе — " +
		"ОБЯЗАТЕЛЬНО проставь questline_id_ref на индекс create_questline " +
		"action'а, не забывай это поле.\n" +
		"  • update_quest — изменить СУЩЕСТВУЮЩИЙ квест (обязателен quest_id из " +
		"тега quest=N, или quest_id_ref если квест создаётся в этом же батче): " +
		"статус, title, pinned, значимость, и ГЛАВНОЕ — прикрепление к квестлайну " +
		"(questline_id из тега questline=N, questline_id_ref если квестлайн " +
		"создаётся тут же, или questline как имя уже существующего для резолва " +
		"по подстроке; clear_questline=true — отвязать).\n" +
		"  • add_step — добавить НОВЫЙ шаг внутрь существующего квеста (quest_id " +
		"из тега quest=N). title обязателен, steps не используется.\n" +
		"  • update_step / delete_step — quest_id + step_id (оба из тегов).\n" +
		"Примеры:\n" +
		"  \"создай квестлайн Бэкапы и закинь туда quest=42\" →\n" +
		"    [{index:0, action:create_questline, title:\"Бэкапы\"}, " +
		"{index:1, action:update_quest, quest_id:42, questline_id_ref:0}]\n" +
		"  \"перенеси quest=5 в questline=3, поставь completed\" →\n" +
		"    [{index:0, action:update_quest, quest_id:5, questline_id:3, " +
		"status:\"completed\"}]\n" +
		"  \"quest=9 сделай completed и создай квестлайн Инфраструктура, закинь " +
		"его туда\" →\n" +
		"    [{index:0, action:update_quest, quest_id:9, status:\"completed\"}, " +
		"{index:1, action:create_questline, title:\"Инфраструктура\"}, " +
		"{index:2, action:update_quest, quest_id:9, questline_id_ref:1}]\n" +
		"  \"создай квестлайн Мониторинг с квестом Настроить графану\" →\n" +
		"    [{index:0, action:create_questline, title:\"Мониторинг\"}, " +
		"{index:1, action:create_quest, title:\"Настроить графану\", " +
		"questline_id_ref:0}]\n" +
		"Верни ОДИН JSON-объект по схеме, без пояснений вне JSON. Поля, не нужные " +
		"для конкретного action, оставляй null (clear_questline=false по " +
		"умолчанию, steps=null кроме create_quest с явными шагами).\n" +
		"status один из: active, delayed, completed, failed, archived.\n" +
		"needs_clarification=true (actions=[]) только если запрос реально " +
		"неоднозначен (непонятно, какой квест/шаг/квестлайн имеется в виду и " +
		"тег/имя не помогает установить это однозначно).\n" +
		"JSON Schema:\n" + string(schema)
}
