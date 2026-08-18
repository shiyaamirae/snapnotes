# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools) for the **Screenshot-to-Notion Pipeline**: a system that captures screenshots via a custom hotkey, has AI read and classify them, extracts the useful content, and appends it in a clean format (table or bullets) to the matching Notion page. This separation of concerns — probabilistic AI for reasoning, deterministic code for execution — is what makes the system reliable.

## Project Context

Screenshots pile up fast when learning from tutorials, tips, and comparisons. Instead of manually renaming and sorting them, this pipeline automates it end to end:

`hotkey → screenshot saved → AI classifies + extracts → content appended to matching Notion page`

Validated in manual testing (Phase 0, 4 screenshots, full pass): correct categorization, clean table-format extraction, and for screenshots that don't fit a category, the AI explained what it was, why it didn't fit, and suggested the closest match. **Preserve this exact "closest match" behavior — do not replace it with a hard "none fit" rejection.**

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- `workflows/route_screenshot.md` — the SOP defining: what counts as a valid screenshot, how classification works, how to format extracted content per category, what to do when nothing matches, and how to handle failures at each stage.
- Written in plain language, the same way you'd brief someone on the team.

**Layer 2: Agents (The Decision-Maker)**
- This is your role. Read `workflows/route_screenshot.md`, run the tools in sequence, handle failures gracefully, and ask before proceeding when something's ambiguous.
- Connect intent to execution without trying to do everything yourself — if a step needs a tool, use the tool, don't hand-roll it inline.

**Layer 3: Tools (The Execution)**
- Python package in `snapnotes/` that does the actual work: watching for new screenshots, calling the Gemini API, writing to Notion.
- Credentials live in `.env` only — never hardcoded, never logged.
- Core tools (build if missing, reuse if present):
  - `snapnotes/watcher.py` — watches `inbox/` (populated by the Hammerspoon-triggered capture) for new screenshot files
  - `snapnotes/gemini_client.py` — sends the screenshot to the Gemini API (Flash-Lite) using the validated Phase 0 prompt, returns category + formatted content as structured JSON
  - `snapnotes/notion_client.py` — appends the formatted content to the matched Notion page via the Notion API, and fetches the live category list from Notion
  - `snapnotes/pipeline.py` — orchestrates one screenshot end to end: classify → file to Notion or `needs_review/` → move the file to `processed/<category>/`, `needs_review/`, or `errors/`
  - `snapnotes/app.py` — menu bar shell (rumps) tying the watcher and pipeline together with status icons and notifications
  - `snapnotes/config.py` / `snapnotes/models.py` — loads `.env` + `config.yaml`, typed config/data models

**Why this matters:** if each step is 90% accurate on its own, five unstructured steps compounds down to ~59% success. Offloading capture, extraction, and writing to deterministic scripts keeps the AI focused on the one place it's actually needed: deciding what a screenshot means and where it belongs.

## How to Operate

**1. Look for existing tools first**
Check `snapnotes/` before writing anything new. Only build a new script when nothing in the folder covers the task.

**2. Learn and adapt when things fail**
When you hit an error:
- Read the full error message and trace before guessing
- Fix the script and retest — but if the fix requires spending paid API calls beyond normal free-tier usage, check with Shiyaa first
- Document what you learned directly in `workflows/route_screenshot.md` (rate limits hit, timing quirks, edge cases)
- Example: Gemini free tier returns a 429 → check whether it's RPM or RPD → if RPM, add exponential backoff with jitter; if RPD, stop and tell Shiyaa rather than silently retrying all day

**3. Keep the workflow current, but don't overwrite without asking**
Workflows should evolve as you learn, but they're Shiyaa's source of truth — propose changes, don't silently rewrite them, unless she's told you explicitly to just go ahead.

## The Self-Improvement Loop

1. Identify what broke
2. Fix the tool
3. Verify the fix actually works (rerun on the same failing input)
4. Update `workflows/route_screenshot.md` with the new approach
5. Move on with a more robust system

## File Structure

```
inbox/          # Screenshots waiting to be processed (Hammerspoon drops captures here).
                 # Disposable — never treat inbox/ as the source of truth.
processed/      # Successfully filed screenshots, moved here as <category>/<file>.
                 # Auto-deleted after 10 days (snapnotes/app.py) — Notion already has the content by then.
needs_review/   # Screenshots where nothing matched a category — check explanation + suggestion in logs.
errors/         # Screenshots that raised an exception mid-processing. Never silently dropped.
logs/           # Rotating pipeline log (snapnotes.log).
snapnotes/      # The Python package: watcher.py, gemini_client.py, notion_client.py, pipeline.py, app.py, config.py, models.py
scripts/        # setup_check.py (doctor script) + standalone test scripts for iterating on Gemini/Notion in isolation
workflows/      # route_screenshot.md — the SOP for this pipeline
hammerspoon/    # init.lua.snippet — hotkey → screencapture → inbox/
config.yaml     # notion_home_url + Gemini model. NOT committed (see .gitignore). Categories are NOT here — read live from Notion.
.env            # GEMINI_API_KEY, NOTION_TOKEN — secrets live ONLY here
```

**Core principle:** Notion is the deliverable — it's what Shiyaa actually opens and reads. Everything in `inbox/` is intermediate and regenerable. If a screenshot fails to process, keep it (in `needs_review/` or `errors/`) and flag it — never silently drop it.

## Project-Specific Rules

- **AI engine is the Gemini API (Flash-Lite), free tier — not the Claude API.** Shiyaa's Claude Pro subscription is chat-only and does not include API credits. Do not assume Claude API access is available unless she's explicitly set up separate billing for it.
- **Categories live as Notion subpages under `notion_home_url`** (e.g. Claude Skills, Codex Tips, Free Models). `snapnotes/notion_client.py::fetch_categories` reads them fresh from Notion on every screenshot — subpage title is the category name, its first paragraph block (if any) is the description. Never hardcode the category list in `config.yaml` or in code; adding a subpage in Notion should be the only step needed to add a category.
- **No sensitive-content handling needed.** These are personal learning screenshots only (tutorials, tips, model comparisons) — Shiyaa has confirmed privacy isn't a concern here, so no need to build a local/offline (Ollama) fallback for this project.
- **Source/provenance metadata is out of scope.** Fullscreen captures won't reliably expose it — not worth engineering around.
- **macOS permissions**: Hammerspoon needs Screen Recording + Accessibility granted for capture and hotkeys to work (it's the process that actually invokes `screencapture`). Terminal only needs Screen Recording if Shiyaa manually runs `screencapture` from the command line for ad-hoc testing — not required for the v1 pipeline itself. If a capture silently fails, check permissions before assuming a code bug — surface this to Shiyaa rather than debugging blind.
- **Versioning is split by concern:** git versions the code in this repo; Notion's native page history versions the actual note content. Don't build a custom versioning layer for either.
- **Review/confirmation step (e.g. "Added to Free Models ✅") is a planned v2 feature, not required for v1.** Don't add it unprompted — ask before scoping it in.

## Validated Extraction Prompt (Phase 0 — tested against 4 screenshots, full pass)

Use this as the base prompt in `snapnotes/gemini_client.py::build_prompt`. The category list below is illustrative only — the real implementation builds it from whatever `fetch_categories` returns from Notion at runtime, never hardcoded.

```
Here are my note categories:
- Claude Skills: notes on Claude's skills/capabilities
- Codex Tips: tips and tricks for OpenAI Codex
- Free Models: which AI models are free and what they're good for

Look at this screenshot and:
1. Decide which category it belongs to (or say "none fit")
2. Extract the useful information
3. Format it as it should be appended to that note — use a
   table if it's comparative data, bullets otherwise
4. Keep it skimmable, not a wall of text
```

If a screenshot doesn't cleanly fit, don't force it — explain what it is, why it doesn't match, and name the closest category anyway. This behavior was explicitly validated and should be preserved.

## Bottom Line

You sit between what Shiyaa wants (the workflow) and what actually gets done (the tools). Read the workflow, call the right tool, recover from errors without losing the screenshot, and keep `route_screenshot.md` current as you learn how this pipeline actually behaves in the wild.

Stay pragmatic. Stay reliable. Ask before spending money or overwriting instructions.
