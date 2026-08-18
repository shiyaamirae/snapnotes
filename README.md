# SnapNotes

Press a hotkey, screenshot gets read by Gemini, extracted content lands as a
structured, skimmable note on the right Notion page — no manual sorting.

Flow: Hammerspoon hotkey -> `screencapture` -> `inbox/` -> watchdog ->
Gemini (classify + extract) -> Notion (append to the matching subpage) ->
menu bar status.

See [SETUP.md](SETUP.md) for first-time setup — `python3.12 -m scripts.install`
handles the mechanical parts (venv, dependencies, credentials, the login
service); a few steps still need a human clicking through macOS/Notion UI.
