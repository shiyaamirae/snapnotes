from __future__ import annotations

import re
from datetime import datetime

from notion_client import Client

from snapnotes.models import (
    CategoryConfig,
    DatabaseExtraction,
    DatabaseSchemaProperty,
    ExtractionResult,
)

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
) -> str:
    client = Client(auth=notion_token)

    if result.content_type == "table":
        children = build_table_children(
            result.title, result.table_headers or [], result.table_rows or []
        )
    else:
        children = build_bullets_children(result.title, result.bullets or [])

    if category.is_database:
        properties = _build_database_properties(
            category.schema_properties or [], field_values, fallback_title=result.title
        )
        row = client.pages.create(
            parent={"data_source_id": category.data_source_id}, properties=properties
        )
        row_id = row["id"]
        client.blocks.children.append(block_id=row_id, children=children)
        return row_id

    response = client.blocks.children.append(block_id=category.notion_page_id, children=children)
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
                categories.append(
                    CategoryConfig(
                        name=block["child_page"]["title"],
                        description=_first_paragraph_text(client, block["id"]),
                        notion_page_id=block["id"],
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
