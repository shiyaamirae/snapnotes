from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from snapnotes import api_usage
from snapnotes.models import (
    AppConfig,
    CategoryConfig,
    DatabaseExtraction,
    ExtractionResult,
    FormattedEntry,
)

logger = logging.getLogger("snapnotes")

RETRYABLE_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 2.0


def _is_daily_quota_error(error: genai_errors.APIError) -> bool:
    text = f"{error.message or ''} {error.details or ''}".lower()
    return "per day" in text or "perday" in text or "daily" in text


def _generate_with_retry(client: genai.Client, **kwargs: Any) -> types.GenerateContentResponse:
    """Gemini's free tier hits real transient 5xx/429s in practice, not just
    theoretically - retries with exponential backoff + jitter for anything
    that looks temporary. A 429 that's specifically a per-day quota error
    won't resolve by waiting a few seconds, so that one raises immediately
    instead of burning retries."""
    last_error: genai_errors.APIError | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            api_usage.record_call()
            return client.models.generate_content(**kwargs)
        except genai_errors.APIError as e:
            last_error = e
            if e.code == 429 and _is_daily_quota_error(e):
                logger.error("Gemini daily quota exceeded, not retrying: %s", e)
                raise
            if e.code not in RETRYABLE_CODES or attempt == MAX_RETRIES:
                raise
            delay = BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
            logger.error(
                "Gemini API error %s (attempt %d/%d), retrying in %.1fs: %s",
                e.code, attempt + 1, MAX_RETRIES, delay, e,
            )
            time.sleep(delay)
    raise last_error  # unreachable, but satisfies type checkers


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

    response = _generate_with_retry(
        client,
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
first one:
- Use a title that reflects the whole screenshot instead (something
  close to "{overview_title}" works well)
- For a single-value field (select), leave it empty rather than picking
  one item to represent all of them, unless one item is clearly the
  primary subject and the rest are secondary context
- For a multi-value or free-text field (multi_select, rich_text), still
  fill it in by aggregating across all the items - e.g. the union of
  what each item is best for, or a summary note covering all of them.
  Don't leave these empty just because several items are covered.
"""


def extract_database_fields(
    image_path: Path, cfg: AppConfig, category: CategoryConfig, overview_title: str
) -> DatabaseExtraction:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = _generate_with_retry(
        client,
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
"table"; anything else is usually "bullets".

Set wrap_in_toggle to true only if the instruction actually describes a
toggle (e.g. "toggle title = ..."). If it instead describes a heading
(e.g. "each entry is a heading"), set wrap_in_toggle to false. Either
way, set title to the toggle summary or heading text the instruction
calls for, kept short.
"""


def extract_formatted_entry(
    image_path: Path, cfg: AppConfig, category: CategoryConfig
) -> FormattedEntry:
    client = genai.Client(api_key=cfg.gemini_api_key)
    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(), mime_type="image/png"
    )

    response = _generate_with_retry(
        client,
        model=cfg.gemini_model,
        contents=[build_format_prompt(category), image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FormattedEntry,
        ),
    )

    return FormattedEntry.model_validate_json(response.text)
