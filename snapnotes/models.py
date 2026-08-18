from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class DatabaseSchemaProperty(BaseModel):
    name: str
    type: str
    options: list[str] = []


class CategoryConfig(BaseModel):
    name: str
    description: str
    notion_page_id: str
    is_database: bool = False
    data_source_id: str | None = None
    schema_properties: list[DatabaseSchemaProperty] | None = None
    format_instructions: str | None = None
    include_screenshot: bool = False


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


class DatabaseFieldValue(BaseModel):
    property: str
    values: list[str]


class DatabaseExtraction(BaseModel):
    fields: list[DatabaseFieldValue]


class FormattedEntry(BaseModel):
    title: str | None = None  # toggle summary or heading text, per wrap_in_toggle
    wrap_in_toggle: bool = True
    content_type: Literal["bullets", "table", "code"]
    bullets: list[str] | None = None
    table_headers: list[str] | None = None
    table_rows: list[list[str]] | None = None
    code_content: str | None = None
    code_language: str | None = None
