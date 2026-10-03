import pytest

from quests import mcp_server


def _n(id, title, parent=None, cat=False, desc="", private=False):
    return {
        "id": id,
        "title": title,
        "parent_id": parent,
        "is_category": cat,
        "is_private": private,
        "description": desc,
    }


VAULT = [
    _n(1, "Гайды", cat=True, desc="## Как что-то делать\nпошаговые инструкции"),
    _n(2, "Гайд по X", parent=1, desc="текст"),
    _n(3, "Вложенная", parent=1, cat=True),
    _n(4, "Глубокая", parent=3, desc="d"),
    _n(5, "Корневая", desc="r"),
    _n(6, "Креды", cat=True, desc="секрет", private=True),
]


@pytest.fixture
def api(monkeypatch):
    calls = []

    def fake(path, query=None):
        calls.append((path, query))
        assert path == "/api/notes"
        if query and "parent_id" in query:
            return [n for n in VAULT if n["parent_id"] == query["parent_id"]]
        return VAULT

    monkeypatch.setattr(mcp_server, "_api_get", fake)
    return calls


def test_categories_listing(api):
    rows = mcp_server.list_note_categories()
    assert [r["id"] for r in rows] == [1, 3, 6]
    g = rows[0]
    assert g["hint"] == "Как что-то делать"
    assert g["children"] == 2
    assert rows[1]["path"] == "Гайды / Вложенная"
    assert rows[2]["hint"] == ""  # private → no hint leaks


def test_category_filter_takes_all_descendants(api):
    ids = [n["id"] for n in mcp_server.list_notes(category_id=1)]
    assert ids == [2, 3, 4]


def test_category_filter_rejects_non_category(api):
    with pytest.raises(ValueError, match="not a CATEGORY"):
        mcp_server.list_notes(category_id=5)
    with pytest.raises(ValueError, match="not found"):
        mcp_server.list_notes(category_id=99)


def test_brief_drops_description(api):
    rows = mcp_server.list_notes(brief=True)
    assert all("description" not in r for r in rows)
    assert rows[1]["description_len"] == 5


def test_create_note_refused_without_parent(api, monkeypatch):
    posted = []
    monkeypatch.setattr(mcp_server, "_api", lambda *a, **k: posted.append((a, k)) or {"id": 7})
    with pytest.raises(ValueError, match="no_category=true") as e:
        mcp_server.create_note(title="Новая")
    assert "note=1 Гайды" in str(e.value)
    assert not posted


def test_create_note_exemptions(api, monkeypatch):
    posted = []
    monkeypatch.setattr(mcp_server, "_api", lambda *a, **k: posted.append(k["body"]) or {"id": 7})
    mcp_server.create_note(title="a", parent_id=1)
    mcp_server.create_note(title="b", no_category=True)
    mcp_server.create_note(title="c", is_category=True)
    assert [b["title"] for b in posted] == ["a", "b", "c"]


def test_create_note_without_categories_is_not_guarded(monkeypatch):
    monkeypatch.setattr(mcp_server, "_api_get", lambda p, q=None: [_n(1, "x")])
    monkeypatch.setattr(mcp_server, "_api", lambda *a, **k: {"id": 2})
    assert mcp_server.create_note(title="t") == {"id": 2}
