from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from snapnotes.models import AppConfig, CategoryConfig, DatabaseExtraction, ExtractionResult


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


def build_database_prompt(category: CategoryConfig) -> str:
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

Extract values for each of these Notion database fields, based only on what's
visible in the screenshot:
{fields_block}

For each field, return its exact name (as given above) and its value(s) as a
list of strings - one string for single-value fields, multiple strings for
multi_select fields. Skip a field entirely if nothing in the screenshot is
relevant to it.
"""


def extract_database_fields(
    image_path: Path, cfg: AppConfig, category: CategoryConfig
) -> DatabaseExtraction:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = client.models.generate_content(
        model=cfg.gemini_model,
        contents=[build_database_prompt(category), image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DatabaseExtraction,
        ),
    )

    return DatabaseExtraction.model_validate_json(response.text)
