from quests.telegram.actions_preview import format_actions_preview


def test_create_shows_everything_the_action_sets():
    text = format_actions_preview(
        {
            "actions": [
                {
                    "index": 0,
                    "action": "create_quest",
                    "title": "Счёт",
                    "description": "до <пятницы>",
                    "significance": "epic",
                    "pinned": True,
                    "deadline_at": "2026-10-05T10:00:00Z",
                    "duration_seconds": 7200,
                    "steps": [{"title": "Оплатить", "description": "в ЛК", "progress_total": 3}],
                }
            ]
        }
    )
    for part in ("до &lt;пятницы&gt;", "эпическое", "закреплён: да", "2 ч 0 мин", "в ЛК", "(0/3)"):
        assert part in text
    assert "05.10 13:00" in text  # Moscow time, not raw UTC ISO


def test_update_shows_before_and_after():
    text = format_actions_preview(
        {"actions": [{"index": 0, "action": "update_quest", "quest_id": 5, "significance": "epic"}]},
        [{"index": 0, "before": {"title": "Старое", "significance": "common"}}],
    )
    assert "«Старое»" in text
    assert "обычное → <b>эпическое</b>" in text


def test_unchanged_fields_are_not_listed():
    text = format_actions_preview(
        {"actions": [{"index": 0, "action": "update_quest", "quest_id": 5, "title": "Тот же", "pinned": True}]},
        [{"index": 0, "before": {"title": "Тот же", "pinned": False}}],
    )
    assert "название" not in text
    assert "закреплён: нет → <b>да</b>" in text


def test_long_plan_fits_telegram_limit_and_keeps_the_question():
    batch = {
        "actions": [
            {"index": i, "action": "create_quest", "title": "x" * 50, "description": "y" * 400}
            for i in range(40)
        ]
    }
    text = format_actions_preview(batch)
    assert len(text) <= 4096
    assert text.endswith("Применить этот план?")
    assert text.count("<b>") == text.count("</b>")
