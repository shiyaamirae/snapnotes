"""One-time setup for a new SnapNotes install: creates the venv, installs
dependencies, collects credentials, and registers the background service.

Run with the SYSTEM's python3.12 (not from .venv, which doesn't exist yet):

    python3.12 -m scripts.install

This only sets up the pipeline itself - it doesn't touch Hammerspoon,
Notion permissions, or anything requiring a GUI. See SETUP.md for those,
and run scripts/bootstrap_categories.py afterward for a starter set of
Notion categories.
"""
from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
ENV_FILE = REPO_ROOT / ".env"
CONFIG_FILE = REPO_ROOT / "config.yaml"
CONFIG_EXAMPLE = REPO_ROOT / "config.example.yaml"
PLIST_TEMPLATE = REPO_ROOT / "scripts" / "launchd" / "com.shiyaa.snapnotes.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def _find_python312() -> str:
    for candidate in ("python3.12", "/opt/homebrew/bin/python3.12", "/usr/local/bin/python3.12"):
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    print("FAIL: python3.12 not found. Install it first: brew install python@3.12")
    sys.exit(1)


def _create_venv(python312: str) -> Path:
    venv_python = VENV_DIR / "bin" / "python"
    if venv_python.exists():
        print(f"OK: .venv already exists at {VENV_DIR}")
        return venv_python
    print("Creating .venv...")
    subprocess.run([python312, "-m", "venv", str(VENV_DIR)], check=True)
    print("Installing dependencies (this can take a minute)...")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-q", "-r", str(REPO_ROOT / "requirements.txt")],
        check=True,
    )
    print("OK: .venv ready")
    return venv_python


def _write_env() -> None:
    if ENV_FILE.exists():
        print(f"OK: {ENV_FILE} already exists, leaving it as-is")
        return
    print("\n--- Credentials ---")
    print("Gemini API key: create one at Google AI Studio (aistudio.google.com)")
    gemini_key = getpass.getpass("Paste your GEMINI_API_KEY: ").strip()
    print("Notion integration token: create one at notion.so/my-integrations")
    print("(choose 'Access token', not OAuth)")
    notion_token = getpass.getpass("Paste your NOTION_TOKEN: ").strip()
    ENV_FILE.write_text(f"GEMINI_API_KEY={gemini_key}\nNOTION_TOKEN={notion_token}\n")
    print(f"OK: wrote {ENV_FILE}")


def _write_config() -> None:
    if CONFIG_FILE.exists():
        print(f"OK: {CONFIG_FILE} already exists, leaving it as-is")
        return
    print("\n--- Notion home page ---")
    print("Create a home page in Notion for SnapNotes, share it with your")
    print("integration (\"...\" menu -> Connections), then paste its URL below.")
    home_url = input("Notion home page URL: ").strip()
    template = CONFIG_EXAMPLE.read_text()
    template = template.replace('"TODO_PASTE_MAIN_PAGE_URL"', f'"{home_url}"')
    CONFIG_FILE.write_text(template)
    print(f"OK: wrote {CONFIG_FILE}")


def _check_tool(name: str, brew_install_cmd: str) -> None:
    if shutil.which(name):
        print(f"OK: {name} found")
    else:
        print(f"TODO: {name} not found - install with: {brew_install_cmd}")


def _install_launchd(venv_python: Path) -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    label = f"com.{getpass.getuser()}.snapnotes"
    plist_path = LAUNCH_AGENTS_DIR / f"{label}.plist"

    content = PLIST_TEMPLATE.read_text()
    content = content.replace("__LABEL__", label)
    content = content.replace("__VENV_PYTHON__", str(venv_python))
    content = content.replace("__REPO_ROOT__", str(REPO_ROOT))
    plist_path.write_text(content)

    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"OK: registered and started as a login service ({label})")
    else:
        print(f"FAIL: launchctl bootstrap failed: {result.stderr.strip()}")


def main() -> int:
    print("=== SnapNotes setup ===\n")
    python312 = _find_python312()
    venv_python = _create_venv(python312)
    _write_env()
    _write_config()

    print("\n--- Other tools SnapNotes needs ---")
    _check_tool("hs", "brew install --cask hammerspoon")  # `hs` CLI ships with the cask
    _check_tool("terminal-notifier", "brew install terminal-notifier")

    print("\n--- Registering background service ---")
    _install_launchd(venv_python)

    print("\n--- Verifying ---")
    subprocess.run([str(venv_python), "-m", "scripts.setup_check"], cwd=REPO_ROOT)

    print("\nDone. Remaining manual steps (see SETUP.md):")
    print("  1. If Hammerspoon isn't installed/configured: launch it, grant")
    print("     Accessibility + Screen Recording, merge hammerspoon/init.lua.snippet")
    print("     into ~/.hammerspoon/init.lua, reload its config.")
    print("  2. If terminal-notifier just got installed, it'll ask for a one-time")
    print("     notification permission the first time SnapNotes tries to notify you.")
    print("  3. Add category subpages/databases under your Notion home page - or run")
    print("     `.venv/bin/python -m scripts.bootstrap_categories` for a starter set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
