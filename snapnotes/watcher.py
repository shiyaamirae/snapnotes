from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from snapnotes.config import REPO_ROOT

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class InboxHandler(FileSystemEventHandler):
    def __init__(self, on_new_file: Callable[[Path], None]):
        self.on_new_file = on_new_file

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            return
        if not self._wait_until_stable(path):
            return
        self.on_new_file(path)

    @staticmethod
    def _wait_until_stable(path: Path, checks: int = 2, interval: float = 0.3) -> bool:
        try:
            last_size = -1
            for _ in range(checks + 3):
                if not path.exists():
                    return False
                size = path.stat().st_size
                if size == last_size and size > 0:
                    return True
                last_size = size
                time.sleep(interval)
            return path.exists()
        except FileNotFoundError:
            return False


def start_watching(on_new_file: Callable[[Path], None], inbox: Path | None = None) -> Observer:
    inbox = inbox or (REPO_ROOT / "inbox")
    observer = Observer()
    observer.schedule(InboxHandler(on_new_file), str(inbox), recursive=False)
    observer.start()
    return observer


if __name__ == "__main__":
    obs = start_watching(lambda p: print(f"New screenshot: {p}"))
    print(f"Watching {REPO_ROOT / 'inbox'} ... Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
        obs.join()
