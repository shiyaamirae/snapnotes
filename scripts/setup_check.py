"""Doctor script: run `python -m scripts.setup_check` from the repo root
to check whether SnapNotes is configured correctly before wiring it up."""
from __future__ import annotations

import sys

from snapnotes.config import load_config, validate_config
from snapnotes.notion_client import extract_page_id, fetch_categories, verify_page_access


def main() -> int:
    try:
        cfg = load_config()
    except FileNotFoundError as e:
        print(f"FAIL: {e}")
        return 1

    problems = validate_config(cfg)
    if problems:
        for p in problems:
            print(f"FAIL: {p}")
        return 1

    print("OK: config loaded, keys present")

    home_page_id = extract_page_id(cfg.notion_home_url)
    if not verify_page_access(cfg.notion_token, home_page_id):
        print("FAIL: no Notion access to notion_home_url (check it's shared with the integration)")
        return 1
    print("OK: Notion access to home page")

    categories = fetch_categories(cfg.notion_token, cfg.notion_home_url)
    if not categories:
        print("FAIL: no subpages found under notion_home_url (create one per category)")
        return 1

    print(f"OK: found {len(categories)} categories live from Notion:")
    all_ok = True
    for cat in categories:
        desc = f" - {cat.description}" if cat.description else ""
        kind = "database" if cat.is_database else "page"
        print(f"  - {cat.name} [{kind}]{desc}")
        if cat.is_database:
            props = cat.schema_properties or []
            if not any(p.type == "title" for p in props):
                print("    FAIL: no writable title property found on this database")
                all_ok = False
            else:
                print(f"    fields: {', '.join(p.name for p in props)}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
