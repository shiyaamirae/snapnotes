from snapnotes.models import AppConfig
from snapnotes.config import validate_config


def _cfg(**overrides) -> AppConfig:
    base = dict(
        gemini_api_key="key",
        notion_token="token",
        notion_home_url="https://notion.so/home-abc123",
        gemini_model="gemini-flash-lite-latest",
    )
    base.update(overrides)
    return AppConfig(**base)


def test_valid_config_has_no_problems():
    assert validate_config(_cfg()) == []


def test_missing_gemini_key_is_flagged():
    problems = validate_config(_cfg(gemini_api_key=""))
    assert any("GEMINI_API_KEY" in p for p in problems)


def test_placeholder_home_url_is_flagged():
    problems = validate_config(_cfg(notion_home_url="TODO_PASTE_MAIN_PAGE_URL"))
    assert any("notion_home_url" in p for p in problems)
