#!/usr/bin/env bash
# Export OpenAPI JSON for contract review / Go port.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/openapi.json}"
cd "$ROOT"
uv run python -c "
from pathlib import Path
import json
from quests.main import app
Path('$OUT').write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')
print('wrote', '$OUT')
"
