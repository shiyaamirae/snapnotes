from __future__ import annotations

import logging
import queue
import shutil
import subprocess
import traceback
import webbrowser
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rumps

from snapnotes.config import REPO_ROOT, load_config
from snapnotes.pipeline import process_screenshot  # noqa: F401  (sets up the "snapnotes" logger)
from snapnotes.watcher import start_watching

logger = logging.getLogger("snapnotes")

ICONS = {
    "idle": "●",
    "processing": "◐",
    "filed": "✓",
    "needs_review": "?",
    "error": "!",
}

# launchd runs with a minimal PATH (no /opt/homebrew/bin), so PATH lookup
# alone isn't reliable - resolve once at import time, checking common
# Homebrew locations as a fallback for when $PATH doesn't include it.
_TERMINAL_NOTIFIER = shutil.which("terminal-notifier") or next(
    (p for p in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier") if Path(p).exists()),
    None,
)


def _notify(subtitle: str, message: str) -> None:
    """rumps.notification is unreliable on modern macOS for an unbundled
    script - terminal-notifier is a signed helper that actually delivers."""
    if not _TERMINAL_NOTIFIER:
        logger.error("terminal-notifier not found, skipping notification")
        return
    try:
        result = subprocess.run(
            [_TERMINAL_NOTIFIER, "-title", "SnapNotes", "-subtitle", subtitle, "-message", message],
            capture_output=True,
            text=True,
        )
        logger.info(
            "terminal-notifier rc=%s stdout=%r stderr=%r", result.returncode, result.stdout, result.stderr
        )
    except Exception:
        logger.error("terminal-notifier call failed:\n%s", traceback.format_exc())


class SnapNotesApp(rumps.App):
    def __init__(self):
        super().__init__("SnapNotes", title=ICONS["idle"])
        self.cfg = load_config()
        self.status_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.recent: deque[str] = deque(maxlen=5)
        self.executor = ThreadPoolExecutor(max_workers=2)

        self.recent_menu = rumps.MenuItem("Recent Captures")
        self.menu = [
            self.recent_menu,
            None,
            rumps.MenuItem("Open Notion", callback=self._open_notion),
            rumps.MenuItem("Open Inbox Folder", callback=self._open_inbox),
            rumps.MenuItem("Open Needs Review", callback=self._open_needs_review),
        ]

        self.observer = start_watching(self._handle_new_file)
        self.status_timer = rumps.Timer(self._drain_status_queue, 0.5)
        self.status_timer.start()

    def _handle_new_file(self, path: Path):
        self.status_queue.put(("processing", path.name))
        self.executor.submit(self._process, path)

    def _process(self, path: Path):
        result = process_screenshot(path, self.cfg)
        self.status_queue.put((result.value, path.name))

    def _drain_status_queue(self, _timer):
        try:
            while True:
                status, filename = self.status_queue.get_nowait()
                self.title = ICONS.get(status, ICONS["idle"])
                if status == "filed":
                    self.recent.appendleft(f"{filename} -> filed")
                    self._rebuild_recent_menu()
                    _notify("Filed", filename)
                elif status == "needs_review":
                    self.recent.appendleft(f"{filename} -> needs review")
                    self._rebuild_recent_menu()
                    _notify("Needs review", filename)
                elif status == "error":
                    _notify("Error processing", filename)
        except queue.Empty:
            pass

    def _rebuild_recent_menu(self):
        # rumps.MenuItem's underlying NSMenu doesn't exist until something's
        # been added to it once, so .clear() throws AttributeError on the
        # very first rebuild (before anything's ever been added).
        try:
            self.recent_menu.clear()
        except AttributeError:
            pass
        for entry in self.recent:
            self.recent_menu.add(rumps.MenuItem(entry))

    def _open_notion(self, _sender):
        webbrowser.open(self.cfg.notion_home_url)

    def _open_inbox(self, _sender):
        subprocess.run(["open", str(REPO_ROOT / "inbox")])

    def _open_needs_review(self, _sender):
        subprocess.run(["open", str(REPO_ROOT / "needs_review")])


if __name__ == "__main__":
    SnapNotesApp().run()
