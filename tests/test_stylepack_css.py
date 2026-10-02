from overlay.stylepacks import build_css, list_pack_ids


def test_every_pack_renders_fully_resolved_css():
    ids = list_pack_ids()
    assert ids
    for pack_id in ids:
        css = build_css(pack_id)
        assert "window" in css and ".hud" in css, pack_id
        assert "${" not in css, f"{pack_id}: unresolved template expression"
