"""Render a pack's CSS template from ``overlay/stylepacks/css/``.

Templates are plain CSS; ``${expr}`` is replaced by the value of a Python
expression evaluated against the pack's palette/locals (e.g. ``${_rgba(t.fg, 0.5)}``).
The files are trusted package data, not user input.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_CSS_DIR = Path(__file__).with_name("css")
_EXPR = re.compile(r"\$\{(.+?)\}", re.DOTALL)


def render_css(name: str, namespace: dict[str, Any]) -> str:
    text = (_CSS_DIR / name).read_text(encoding="utf-8")
    return _EXPR.sub(lambda m: str(eval(m.group(1), namespace)), text)
