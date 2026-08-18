from __future__ import annotations

import shutil
import sys
import traceback
from enum import Enum
from pathlib import Path
from typing import Callable

from snapnotes import gemini_client, notion_client
from snapnotes.config import REPO_ROOT, load_config
from snapnotes.logging_setup import setup_logging
from snapnotes.models import AppConfig, CategoryConfig

logger = setup_logging(interactive=True)


class ProcessResult(str, Enum):
    FILED = "filed"
    NEEDS_REVIEW = "needs_review"
    ERROR = "error"


def _category_for(categories: list[CategoryConfig], category_name: str) -> CategoryConfig | None:
    for cat in categories:
        if cat.name == category_name:
            return cat
    return None


def process_screenshot(
    path: Path, cfg: AppConfig, on_status: Callable[[str], None] = lambda s: None
) -> ProcessResult:
    try:
        on_status("processing")
        categories = notion_client.fetch_categories(cfg.notion_token, cfg.notion_home_url)
        result = gemini_client.classify_and_extract(path, cfg, categories)

        category = _category_for(categories, result.matched_category) if result.matched_category else None

        if category:
            if category.is_database:
                field_values = gemini_client.extract_database_fields(path, cfg, category)
                notion_client.append_entry(cfg.notion_token, category, result, field_values=field_values)
            else:
                notion_client.append_entry(cfg.notion_token, category, result)
            dest_dir = REPO_ROOT / "processed" / result.matched_category
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest_dir / path.name))
            logger.info("Filed %s under %s", path.name, result.matched_category)
            on_status("done")
            return ProcessResult.FILED

        dest_dir = REPO_ROOT / "needs_review"
        shutil.move(str(path), str(dest_dir / path.name))
        logger.info(
            "No category matched for %s. Explanation: %s. Suggested: %s",
            path.name,
            result.explanation,
            result.suggested_category,
        )
        on_status("needs_review")
        return ProcessResult.NEEDS_REVIEW

    except Exception:
        logger.error("Failed to process %s:\n%s", path.name, traceback.format_exc())
        try:
            dest_dir = REPO_ROOT / "errors"
            shutil.move(str(path), str(dest_dir / path.name))
        except Exception:
            pass
        on_status("error")
        return ProcessResult.ERROR


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m snapnotes.pipeline <path-to-screenshot>")
        sys.exit(1)

    cfg = load_config()
    outcome = process_screenshot(Path(sys.argv[1]), cfg, on_status=print)
    print(f"Result: {outcome.value}")
