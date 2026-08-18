"""Creates a starter set of category subpages under your Notion home page.

Run after `python -m scripts.install` has set up .env and config.yaml, and
after you've created + shared the home page in Notion:

    .venv/bin/python -m scripts.bootstrap_categories

These are just a starting point - rename them, delete them, add your own,
or add a "Format:"/"Include screenshot: yes" instruction under any of
them, all directly in Notion. Nothing here is hardcoded into the pipeline.
"""
from __future__ import annotations

import sys

from notion_client import Client

from snapnotes.config import load_config
from snapnotes.notion_client import extract_page_id

DEFAULT_CATEGORIES = {
    "Claude Skills": "Notes on Claude's skills and capabilities.",
    "Codex Tips": "Tips and tricks for OpenAI Codex.",
    "Free Models": "Which AI models are free and what they're good for.",
}


def _create_category_page(client: Client, parent_id: str, name: str, description: str) -> None:
    client.pages.create(
        parent={"page_id": parent_id},
        properties={"title": {"title": [{"text": {"content": name}}]}},
        children=[
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"emoji": "📌"},
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": "What this page is for: "},
                            "annotations": {"bold": True},
                        },
                        {"type": "text", "text": {"content": description}},
                    ],
                },
            }
        ],
    )


def main() -> int:
    cfg = load_config()
    if not cfg.notion_home_url or cfg.notion_home_url.startswith("TODO"):
        print("FAIL: config.yaml has no notion_home_url set yet - run scripts.install first")
        return 1

    client = Client(auth=cfg.notion_token)
    home_page_id = extract_page_id(cfg.notion_home_url)

    print("Creating starter categories under your SnapNotes home page...")
    for name, description in DEFAULT_CATEGORIES.items():
        try:
            _create_category_page(client, home_page_id, name, description)
            print(f"  OK: {name}")
        except Exception as e:
            print(f"  FAIL: {name} - {e}")

    print("\nDone. Edit these anytime in Notion - names, descriptions, and Format:")
    print("instructions are all read live, no code change needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
