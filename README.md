# SnapNotes

Press a hotkey, screenshot gets read by Gemini, extracted content lands as a
structured, skimmable note on the right Notion page — no manual sorting.

Flow: Hammerspoon hotkey -> `screencapture` -> `inbox/` -> watchdog ->
Gemini (classify + extract) -> Notion (append to the matching subpage) ->
menu bar status.

See [SETUP.md](SETUP.md) for first-time setup — `python3.12 -m scripts.install`
handles the mechanical parts (venv, dependencies, credentials, the login
service); a few steps still need a human clicking through macOS/Notion UI.

## Notion pages fed

| Page | Format | Content |
|---|---|---|
| Free Models | Database | Model, best-for tags, provider, free-tier details |
| Portfolio Ideas | Toggle list | Source + what stood out |
| Prompts | Toggle list | Summary as title, full prompt inside |
| Case Study Tips | Headings + bullets | Tips, must-haves, don'ts |

New pages get picked up automatically — no hardcoded category list. Seed a
new page with one example entry so the format (table/toggle/headings) has
something to match. Anything the AI can't confidently place lands in
`needs_review/` instead of getting force-filed.

## Stack

- Hammerspoon — hotkey + capture
- Python (watchdog) — folder watcher / orchestration
- Gemini API (Flash-Lite, free tier) — classify + extract
- Notion API — writes the result to the matching page
- launchd — runs SnapNotes as a login service
- terminal-notifier — capture/filing notifications

## License

This project is licensed under the MIT License — see the LICENSE file for details.
