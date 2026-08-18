from __future__ import annotations

import re
from datetime import datetime

from notion_client import Client

from snapnotes.models import (
    CategoryConfig,
    DatabaseExtraction,
    DatabaseSchemaProperty,
    ExtractionResult,
    FormattedEntry,
)

SAFE_CODE_LANGUAGES = {
    "javascript", "typescript", "python", "json", "yaml", "markdown",
    "bash", "shell", "html", "css", "sql", "java", "c", "c++", "c#",
    "go", "rust", "ruby", "php", "plain text",
}

WRITABLE_PROPERTY_TYPES = {
    "title",
    "rich_text",
    "select",
    "multi_select",
    "number",
    "url",
    "checkbox",
    "date",
}


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


def _bullet_item_blocks(bullets: list[str]) -> list[dict]:
    return [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": b}}]},
        }
        for b in bullets
    ]


def _plain_table_block(headers: list[str], rows: list[list[str]]) -> dict:
    def row_block(cells: list[str]) -> dict:
        return {
            "object": "block",
            "type": "table_row",
            "table_row": {
                "cells": [[{"type": "text", "text": {"content": cell}}] for cell in cells]
            },
        }

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "has_row_header": False,
            "children": [row_block(headers)] + [row_block(r) for r in rows],
        },
    }


def _code_block(content: str, language: str | None) -> dict:
    safe_language = language.strip().lower() if language else "plain text"
    if safe_language not in SAFE_CODE_LANGUAGES:
        safe_language = "plain text"
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": content}}],
            "language": safe_language,
        },
    }


def build_toggle_children(entry: FormattedEntry, fallback_title: str) -> list[dict]:
    """A toggle-wrapped entry, per a category's own "Format:" instruction
    (e.g. Prompts wants toggle+code block, Portfolio Ideas wants toggle+bullets).
    No heading/timestamp - the toggle title itself is the visible label."""
    if entry.content_type == "code":
        inner = [_code_block(entry.code_content or "", entry.code_language)]
    elif entry.content_type == "table":
        inner = [_plain_table_block(entry.table_headers or [], entry.table_rows or [])]
    else:
        inner = _bullet_item_blocks(entry.bullets or [])

    toggle_block = {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": entry.toggle_title or fallback_title}}],
            "children": inner,
        },
    }
    return [toggle_block, {"object": "block", "type": "divider", "divider": {}}]


def _data_source_schema(client: Client, database_id: str) -> tuple[str, list[DatabaseSchemaProperty]]:
    """Notion's 2025-09-03 API splits a database from its data source: the
    writable property schema lives on the data source, and pages.create needs
    a data_source_id (not a database_id) as the parent."""
    database = client.databases.retrieve(database_id=database_id)
    data_source_id = database["data_sources"][0]["id"]
    data_source = client.data_sources.retrieve(data_source_id=data_source_id)

    properties: list[DatabaseSchemaProperty] = []
    for name, prop in data_source["properties"].items():
        prop_type = prop["type"]
        if prop_type not in WRITABLE_PROPERTY_TYPES:
            continue  # e.g. created_time/formula/rollup are computed, not writable
        options: list[str] = []
        if prop_type == "select":
            options = [o["name"] for o in prop["select"]["options"]]
        elif prop_type == "multi_select":
            options = [o["name"] for o in prop["multi_select"]["options"]]
        properties.append(DatabaseSchemaProperty(name=name, type=prop_type, options=options))

    return data_source_id, properties


def _build_database_properties(
    schema_properties: list[DatabaseSchemaProperty],
    field_values: DatabaseExtraction | None,
    fallback_title: str,
) -> dict:
    schema_by_name = {p.name: p for p in schema_properties}
    payload: dict = {}

    for fv in (field_values.fields if field_values else []):
        prop = schema_by_name.get(fv.property)
        if not prop or not fv.values:
            continue
        if prop.type == "title":
            payload[prop.name] = {"title": [{"text": {"content": fv.values[0]}}]}
        elif prop.type == "rich_text":
            payload[prop.name] = {"rich_text": [{"text": {"content": fv.values[0]}}]}
        elif prop.type == "select":
            payload[prop.name] = {"select": {"name": fv.values[0]}}
        elif prop.type == "multi_select":
            payload[prop.name] = {"multi_select": [{"name": v} for v in fv.values]}
        elif prop.type == "number":
            try:
                payload[prop.name] = {"number": float(fv.values[0])}
            except ValueError:
                pass
        elif prop.type == "url":
            payload[prop.name] = {"url": fv.values[0]}
        elif prop.type == "checkbox":
            payload[prop.name] = {"checkbox": fv.values[0].strip().lower() in ("true", "yes", "1")}
        elif prop.type == "date":
            payload[prop.name] = {"date": {"start": fv.values[0]}}

    title_prop = next((p for p in schema_properties if p.type == "title"), None)
    if title_prop and title_prop.name not in payload:
        payload[title_prop.name] = {"title": [{"text": {"content": fallback_title}}]}

    return payload


def append_entry(
    notion_token: str,
    category: CategoryConfig,
    result: ExtractionResult,
    field_values: DatabaseExtraction | None = None,
    formatted_entry: FormattedEntry | None = None,
) -> str:
    client = Client(auth=notion_token)

    if category.is_database:
        if result.content_type == "table":
            children = build_table_children(
                result.title, result.table_headers or [], result.table_rows or []
            )
        else:
            children = build_bullets_children(result.title, result.bullets or [])
        properties = _build_database_properties(
            category.schema_properties or [], field_values, fallback_title=result.title
        )
        row = client.pages.create(
            parent={"data_source_id": category.data_source_id}, properties=properties
        )
        row_id = row["id"]
        client.blocks.children.append(block_id=row_id, children=children)
        return row_id

    if formatted_entry is not None:
        children = build_toggle_children(formatted_entry, fallback_title=result.title)
    elif result.content_type == "table":
        children = build_table_children(
            result.title, result.table_headers or [], result.table_rows or []
        )
    else:
        children = build_bullets_children(result.title, result.bullets or [])

    response = client.blocks.children.append(block_id=category.notion_page_id, children=children)
    return response.get("results", [{}])[0].get("id", "")


def verify_page_access(notion_token: str, page_id: str) -> bool:
    client = Client(auth=notion_token)
    try:
        client.pages.retrieve(page_id=page_id)
        return True
    except Exception:
        return False


def _block_text(block: dict) -> str:
    block_type = block.get("type")
    rich_text = block.get(block_type, {}).get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in rich_text).strip()


def _description_and_format(client: Client, page_id: str) -> tuple[str, str | None]:
    """Best-effort description + format instruction: the plain text of a
    category subpage's first paragraph or callout block (e.g. a "What this
    page is for:" note), plus a nested "Format:" child block under it, if
    either exists. Format instructions are kept separate from the
    description since they're only used once a category has already
    matched, not during classification."""
    try:
        children = client.blocks.children.list(block_id=page_id, page_size=5)
    except Exception:
        return "", None

    for block in children.get("results", []):
        block_type = block.get("type")
        if block_type not in ("paragraph", "callout"):
            continue
        description = _block_text(block)
        if not description:
            continue

        format_instructions = None
        if block.get("has_children"):
            try:
                sub_blocks = client.blocks.children.list(block_id=block["id"], page_size=5)
                for sub_block in sub_blocks.get("results", []):
                    text = _block_text(sub_block)
                    if text.lower().startswith("format:"):
                        format_instructions = text
                        break
            except Exception:
                pass

        return description, format_instructions
    return "", None


def _database_description(client: Client, database_id: str) -> str:
    try:
        database = client.databases.retrieve(database_id=database_id)
    except Exception:
        return ""
    rich_text = database.get("description", [])
    return "".join(t.get("plain_text", "") for t in rich_text).strip()


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
            block_type = block.get("type")
            if block_type == "child_page":
                description, format_instructions = _description_and_format(client, block["id"])
                categories.append(
                    CategoryConfig(
                        name=block["child_page"]["title"],
                        description=description,
                        notion_page_id=block["id"],
                        format_instructions=format_instructions,
                    )
                )
            elif block_type == "child_database":
                data_source_id, schema_properties = _data_source_schema(client, block["id"])
                categories.append(
                    CategoryConfig(
                        name=block["child_database"]["title"],
                        description=_database_description(client, block["id"]),
                        notion_page_id=block["id"],
                        is_database=True,
                        data_source_id=data_source_id,
                        schema_properties=schema_properties,
                    )
                )
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")

    return categories
