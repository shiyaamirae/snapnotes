from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CategoryConfig(BaseModel):
    name: str
    description: str
    notion_page_id: str


class AppConfig(BaseModel):
    gemini_api_key: str
    notion_token: str
    notion_home_url: str
    gemini_model: str


class ExtractionResult(BaseModel):
    matched_category: str | None
    title: str
    content_type: Literal["table", "bullets"]
    table_headers: list[str] | None = None
    table_rows: list[list[str]] | None = None
    bullets: list[str] | None = None
    explanation: str
    suggested_category: str | None = None
