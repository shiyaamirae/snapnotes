"""Run `python -m scripts.test_gemini_standalone <path-to-screenshot>`
to sanity-check classification+extraction without touching Notion."""
from __future__ import annotations

import sys
from pathlib import Path

from snapnotes.config import load_config
from snapnotes.gemini_client import classify_and_extract
from snapnotes.notion_client import fetch_categories


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.test_gemini_standalone <path-to-screenshot>")
        return 1

    cfg = load_config()
    categories = fetch_categories(cfg.notion_token, cfg.notion_home_url)
    result = classify_and_extract(Path(sys.argv[1]), cfg, categories)
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
