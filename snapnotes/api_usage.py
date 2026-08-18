from __future__ import annotations

import json
from datetime import date
from threading import Lock

from snapnotes.config import REPO_ROOT

USAGE_FILE = REPO_ROOT / "logs" / "api_usage.json"
_lock = Lock()


def _load() -> dict:
    if not USAGE_FILE.exists():
        return {}
    try:
        return json.loads(USAGE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def record_call() -> None:
    """Call once per Gemini API request - a screenshot can trigger up to two
    (classify, then a scoped extraction for database/format categories)."""
    with _lock:
        data = _load()
        today = date.today().isoformat()
        data[today] = data.get(today, 0) + 1
        _save(data)


def today_count() -> int:
    return _load().get(date.today().isoformat(), 0)
