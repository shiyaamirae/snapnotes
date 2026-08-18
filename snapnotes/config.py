from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from snapnotes.models import AppConfig

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_config(root: Path = REPO_ROOT) -> AppConfig:
    load_dotenv(root / ".env")

    config_path = root / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"{config_path} not found. Copy config.example.yaml to config.yaml and fill it in."
        )
    raw = yaml.safe_load(config_path.read_text()) or {}

    return AppConfig(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        notion_token=os.environ.get("NOTION_TOKEN", ""),
        notion_home_url=raw.get("notion_home_url", ""),
        gemini_model=(raw.get("gemini") or {}).get("model", "gemini-flash-lite-latest"),
    )


def validate_config(cfg: AppConfig) -> list[str]:
    problems: list[str] = []

    if not cfg.gemini_api_key:
        problems.append("GEMINI_API_KEY is missing (set it in .env)")
    if not cfg.notion_token:
        problems.append("NOTION_TOKEN is missing (set it in .env)")
    if not cfg.notion_home_url or cfg.notion_home_url.startswith("TODO"):
        problems.append("notion_home_url is missing or still a placeholder in config.yaml")

    return problems
