# SnapNotes setup

## Things only you can do (Claude Code can't click through GUIs)

1. Install Hammerspoon: `brew install --cask hammerspoon`, launch it once,
   grant it **Accessibility** and **Screen Recording** permission in
   System Settings -> Privacy & Security.
1b. Install `terminal-notifier`: `brew install terminal-notifier`. It'll
   prompt for notification permission the first time it fires - allow it.
   `rumps.notification` doesn't reliably fire on modern macOS for an
   unbundled script, so `snapnotes/app.py` uses this instead.
2. Hotkey is set to cmd+shift+7 in `hammerspoon/init.lua.snippet` (doesn't
   collide with system shortcuts like cmd+shift+3/4/5). Change it there if
   you want something else.
3. Create a Gemini API key at Google AI Studio -> put it in `.env` as
   `GEMINI_API_KEY`.
4. Create a Notion integration at notion.so/my-integrations (internal
   integration) -> copy its token into `.env` as `NOTION_TOKEN`.
5. In Notion: create a teamspace/section for this, a main page, and one
   subpage per category (e.g. Claude Skills, Codex Tips, Free Models, or
   whatever you land on — the subpage title IS the category name, read
   live at runtime). Optionally give a subpage a first paragraph of body
   text to use as its description in the classification prompt. Share the
   main page with the integration you just created (subpages inherit
   access).
6. Copy the main page's URL into `config.yaml` (copy `config.example.yaml`
   first) as `notion_home_url`. Categories aren't listed in `config.yaml` —
   they're read from Notion every run, so adding a subpage later needs no
   config change.
7. Once the above is done, run the doctor script to confirm everything's
   wired up:
   ```
   python -m scripts.setup_check
   ```

## Build/verify order (for reference — see the plan for full detail)

1. `brew install python@3.12`, create `.venv` from it, `pip install -r requirements.txt`.
2. `python -m scripts.setup_check` — config + Notion access.
3. `python -m scripts.test_gemini_standalone <screenshot>` — iterate on the
   prompt in `snapnotes/gemini_client.py` until it matches Phase 0 quality.
4. `python -m scripts.test_notion_standalone "<Category Name>"` — confirms
   a real append works and looks right in Notion.
5. `python -m snapnotes.pipeline <screenshot>` — full one-shot pipeline.
6. `python -m snapnotes.watcher` — drop a file into `inbox/` manually,
   confirm it's picked up.
7. `python -m snapnotes.app` — menu bar shell; confirm icon states and
   notifications work (uses `terminal-notifier`, see step 1b above).
8. Wire up the Hammerspoon hotkey (merge `hammerspoon/init.lua.snippet`
   into `~/.hammerspoon/init.lua`, reload config).
9. Fill in `scripts/launchd/com.shiyaa.snapnotes.plist` placeholders and
   load it so SnapNotes starts automatically at login.
10. End-to-end test with a real screenshot via the actual hotkey, plus one
    deliberately off-topic screenshot to confirm the `needs_review` path.
