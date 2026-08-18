from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from snapnotes.models import (
    AppConfig,
    CategoryConfig,
    DatabaseExtraction,
    ExtractionResult,
    FormattedEntry,
)


def build_prompt(categories: list[CategoryConfig]) -> str:
    category_lines = "\n".join(
        f"- {cat.name}: {cat.description}" if cat.description else f"- {cat.name}"
        for cat in categories
    )
    return f"""Here are my note categories:
{category_lines}

Look at this screenshot and:
1. Decide which category it belongs to (or say none fit)
2. Extract the useful information
3. Format it as it should be appended to that note - use a
   table if it's comparative data, bullets otherwise
4. Keep it skimmable, not a wall of text
5. Give it a specific, recognizable title you'd understand at a glance
   weeks later without opening it: a short label for what kind of content
   this is, followed by the specific named items in parentheses - e.g.
   "Ollama AI Models (Granite, Mistral, Kimi)", not a generic label alone
   ("AI Models Overview") and not a bare comma-separated list with no
   framing ("granite, mistral, kimi"). Name the most notable few items if
   there are many rather than every single one.

If nothing fits, explain what the screenshot is, why it doesn't fit any
category, and suggest the closest matching category.
"""


def classify_and_extract(
    image_path: Path, cfg: AppConfig, categories: list[CategoryConfig]
) -> ExtractionResult:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = client.models.generate_content(
        model=cfg.gemini_model,
        contents=[build_prompt(categories), image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtractionResult,
        ),
    )

    return ExtractionResult.model_validate_json(response.text)


def build_database_prompt(category: CategoryConfig, overview_title: str) -> str:
    field_lines = []
    for prop in category.schema_properties or []:
        if prop.type in ("select", "multi_select") and prop.options:
            field_lines.append(
                f"- {prop.name} ({prop.type}): choose from {prop.options}, "
                "or suggest a new value if none fit"
            )
        else:
            field_lines.append(f"- {prop.name} ({prop.type})")
    fields_block = "\n".join(field_lines)

    return f"""This screenshot matched the "{category.name}" category: {category.description}

The screenshot's overall subject, as already determined, is: "{overview_title}"

Extract values for each of these Notion database fields, based only on what's
visible in the screenshot:
{fields_block}

For each field, return its exact name (as given above) and its value(s) as a
list of strings - one string for single-value fields, multiple strings for
multi_select fields. Skip a field entirely if nothing in the screenshot is
relevant to it.

If the screenshot covers ONE specific item, use its own name for a
title-type field. If it covers MULTIPLE distinct items (a list, search
results, a comparison of several things), do NOT default to just the
first one - use a title that reflects the whole screenshot instead
(something close to "{overview_title}" works well), and leave
single-value fields like a select empty rather than picking one item to
represent all of them, unless one item is clearly the primary subject
and the rest are secondary context.
"""


def extract_database_fields(
    image_path: Path, cfg: AppConfig, category: CategoryConfig, overview_title: str
) -> DatabaseExtraction:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = client.models.generate_content(
        model=cfg.gemini_model,
        contents=[build_database_prompt(category, overview_title), image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DatabaseExtraction,
        ),
    )

    return DatabaseExtraction.model_validate_json(response.text)


def build_format_prompt(category: CategoryConfig) -> str:
    return f"""This screenshot matched the "{category.name}" category: {category.description}

Follow this exact formatting instruction for how to structure the entry:
{category.format_instructions}

Decide the right content_type (bullets, table, or code) based on what's
being captured and the instruction above - e.g. "in a code block" means
content_type "code" with the text in code_content; a comparison implies
"table"; anything else is usually "bullets". If the instruction describes
a toggle title, set toggle_title to that (kept short, per the instruction).
"""


def extract_formatted_entry(
    image_path: Path, cfg: AppConfig, category: CategoryConfig
) -> FormattedEntry:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = client.models.generate_content(
        model=cfg.gemini_model,
        contents=[build_format_prompt(category), image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FormattedEntry,
        ),
    )

    return FormattedEntry.model_validate_json(response.text)
