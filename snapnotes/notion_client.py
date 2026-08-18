from __future__ import annotations

import re
from datetime import datetime

from notion_client import Client

from snapnotes.models import CategoryConfig, ExtractionResult


def extract_page_id(url_or_id: str) -> str:
    """Pull a Notion page ID out of a full page URL, or pass through a bare ID.
    Notion's API accepts IDs with or without dashes, so no need to reformat."""
    last_segment = url_or_id.rstrip("/").split("/")[-1].split("?")[0]
    candidate = last_segment.split("-")[-1]
    if re.fullmatch(r"[0-9a-fA-F]{32}", candidate):
        return candidate
    return last_segment


def _title_block(title: str) -> dict:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {"type": "text", "text": {"content": f"{title}  ·  {stamp}"}}
            ]
        },
    }


def build_table_children(title: str, headers: list[str], rows: list[list[str]]) -> list[dict]:
    def row_block(cells: list[str]) -> dict:
        return {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": cell}}] for cell in cells]
            },
        }

    table_block = {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": [row_block(headers)] + [row_block(r) for r in rows],
        },
    }

    return [_title_block(title), table_block, {"object": "block", "type": "divider", "divider": {}}]


def build_bullets_children(title: str, bullets: list[str]) -> list[dict]:
    bullet_blocks = [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": b}}]
            },
        }
        for b in bullets
    ]
    return [_title_block(title), *bullet_blocks, {"object": "block", "type": "divider", "divider": {}}]


def append_entry(notion_token: str, page_id: str, result: ExtractionResult) -> str:
    client = Client(auth=notion_token)

    if result.content_type == "table":
        children = build_table_children(
            result.title, result.table_headers or [], result.table_rows or []
        )
    else:
        children = build_bullets_children(result.title, result.bullets or [])

    response = client.blocks.children.append(block_id=page_id, children=children)
    return response.get("results", [{}])[0].get("id", "")


def verify_page_access(notion_token: str, page_id: str) -> bool:
    client = Client(auth=notion_token)
    try:
        client.pages.retrieve(page_id=page_id)
        return True
    except Exception:
        return False


def _first_paragraph_text(client: Client, page_id: str) -> str:
    """Best-effort description: the plain text of a category subpage's first
    paragraph block, if it has one. Empty string if there isn't one."""
    try:
        children = client.blocks.children.list(block_id=page_id, page_size=5)
    except Exception:
        return ""

    for block in children.get("results", []):
        if block.get("type") == "paragraph":
            rich_text = block["paragraph"].get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_text).strip()
            if text:
                return text
    return ""


def fetch_categories(notion_token: str, notion_home_url: str) -> list[CategoryConfig]:
    """Categories = subpages directly under the home page in Notion. Reading
    this live (instead of from config.yaml) means a category added in Notion
    shows up on the next screenshot with no code/config change."""
    client = Client(auth=notion_token)
    home_page_id = extract_page_id(notion_home_url)

    categories: list[CategoryConfig] = []
    cursor: str | None = None
    while True:
        response = client.blocks.children.list(block_id=home_page_id, start_cursor=cursor)
        for block in response.get("results", []):
            if block.get("type") != "child_page":
                continue
            categories.append(
                CategoryConfig(
                    name=block["child_page"]["title"],
                    description=_first_paragraph_text(client, block["id"]),
                    notion_page_id=block["id"],
                )
            )
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return categories
