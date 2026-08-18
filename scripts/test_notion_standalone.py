"""Run `python -m scripts.test_notion_standalone "<Category Name>"`
to append a fake test entry to a category's Notion page."""
from __future__ import annotations

import sys

from snapnotes.config import load_config
from snapnotes.models import ExtractionResult
from snapnotes.notion_client import append_entry, fetch_categories


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python -m scripts.test_notion_standalone "<Category Name>"')
        return 1

    category_name = sys.argv[1]
    cfg = load_config()
    categories = fetch_categories(cfg.notion_token, cfg.notion_home_url)
    match = next((c for c in categories if c.name == category_name), None)
    if not match:
        print(f"Unknown category: {category_name}")
        return 1

    fake = ExtractionResult(
        matched_category=category_name,
        title="SnapNotes test entry",
        content_type="bullets",
        bullets=["This is a test entry from test_notion_standalone.py", "Safe to delete"],
        explanation="test",
    )
    append_entry(cfg.notion_token, match.notion_page_id, fake)
    print(f"Appended test entry to '{category_name}'. Check Notion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
