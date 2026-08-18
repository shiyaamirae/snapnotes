# SnapNotes setup

**Requires:** macOS, [Homebrew](https://brew.sh), Python 3.12.

## 1. Get credentials ready

- **Gemini API key** — create one at Google AI Studio (aistudio.google.com).
- **Notion integration token** — create one at notion.so/my-integrations.
  Choose **"Access token"** as the auth method, not OAuth. Copy the
  "Internal Integration Secret."
- **Notion home page** — create a page in Notion for SnapNotes (any name),
  then share it with the integration you just made: "..." menu (top right of the page created)
  → Connections → select your integration from the previous step. Copy the page's URL.

## 2. Run the installer

From the repo root:

```
python3.12 -m scripts.install
```

This creates `.venv`, installs dependencies, prompts you for the two
credentials and the home page URL above (writes `.env`/`config.yaml` —
both are git-ignored, never commit them; this repo is public), checks
whether Hammerspoon and `terminal-notifier` are installed, and
registers SnapNotes as a login service via `launchd`. Safe to re-run —
it skips any step whose file already exists.

Then, optional but recommended for a first run:

```
.venv/bin/python -m scripts.bootstrap_categories
```

Creates a starter set of category subpages under your home page (Claude
Skills, Codex Tips, Free Models) so you're not building the structure by
hand. Skip this if you'd rather add your own categories from scratch —
just create subpages/subdatabases under the home page yourself; names
and descriptions are read live from Notion, no config needed either way.

## 3. Manual steps — no script can do these

- **Install Hammerspoon** (if the installer flagged it missing):
  `brew install --cask hammerspoon`, launch it once, grant it
  **Accessibility** and **Screen Recording** in System Settings → Privacy
  & Security.
- **Install `terminal-notifier`** (if flagged missing):
  `brew install terminal-notifier`. The first notification it sends will
  prompt for permission — allow it. (`rumps.notification` doesn't
  reliably fire on modern macOS for an unbundled script, so `app.py`
  uses this instead.)
- **Wire up the hotkey**: merge [hammerspoon/init.lua.snippet](hammerspoon/init.lua.snippet)
  into `~/.hammerspoon/init.lua` (create the file if it doesn't exist),
  then reload Hammerspoon's config. Default is `cmd+shift+7` for
  full-screen capture, `cmd+shift+8` for crop — edit the snippet first if
  you want different keys (avoid `cmd+shift+3/4/5`, those are taken).

## 4. Verify

```
.venv/bin/python -m scripts.setup_check
```

Confirms config is loaded, credentials are present, the home page is
reachable, and lists every category it can see (with its `Format:`/
`Include screenshot:` settings, if any). Fix whatever it flags before
moving on.

Then a real end-to-end test: press the hotkey, capture something, and
confirm it shows up filed in Notion within a few seconds. Also worth
capturing one deliberately off-topic screenshot to confirm it lands in
`needs_review/` instead of getting force-filed somewhere wrong.

## Doing it by hand instead

If you'd rather skip `scripts.install` and do each piece yourself:

1. `brew install python@3.12`, then `python3.12 -m venv .venv` and
   `.venv/bin/pip install -r requirements.txt`.
2. `cp .env.example .env` and fill in `GEMINI_API_KEY`/`NOTION_TOKEN`.
3. `cp config.example.yaml config.yaml` and fill in `notion_home_url`.
4. Fill in `scripts/launchd/com.shiyaa.snapnotes.plist`'s `__LABEL__`,
   `__VENV_PYTHON__`, and `__REPO_ROOT__` placeholders, copy it to
   `~/Library/LaunchAgents/`, then
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<name>.plist`.
5. Everything in section 3 above still applies.

## Debugging reference: testing one piece at a time

Useful when something's not working and you want to isolate which layer
is broken, rather than a required setup sequence:

1. `.venv/bin/python -m scripts.setup_check` — config + Notion access.
2. `.venv/bin/python -m scripts.test_gemini_standalone <screenshot>` —
   classification/extraction quality in isolation, no Notion write.
3. `.venv/bin/python -m scripts.test_notion_standalone "<Category Name>"`
   — confirms a real append works and looks right in Notion.
4. `.venv/bin/python -m snapnotes.pipeline <screenshot>` — the full
   one-shot pipeline (classify → extract → write → file), no watcher.
5. `.venv/bin/python -m snapnotes.watcher` — drop a file into `inbox/`
   by hand, confirm it's picked up (this only prints detection, doesn't
   process — that's what step 4 or the full app does).
6. `.venv/bin/python -m snapnotes.app` — the real menu bar shell; confirm
   icon states and notifications work.
