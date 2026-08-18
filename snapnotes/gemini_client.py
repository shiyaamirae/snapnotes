from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from snapnotes.models import AppConfig, CategoryConfig, ExtractionResult


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
