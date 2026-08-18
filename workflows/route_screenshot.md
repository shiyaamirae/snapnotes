# SOP: Route a screenshot to Notion

This is the plain-language spec for what the pipeline does to one screenshot,
from the moment it lands in `inbox/` to the moment it's either filed in
Notion or flagged for review. The code in `snapnotes/` implements this; when
the code changes how it behaves, update this file to match.

## 1. What counts as a valid screenshot

- File extension is `.png`, `.jpg`, or `.jpeg`, dropped into `inbox/` (via
  the `cmd+shift+7` full-screen or `cmd+shift+8` crop hotkey, or manually).
- The watcher waits until the file's size stops changing across two checks
  before treating it as "arrived" — this avoids reading a screenshot mid-write.
- `watchdog` only reacts to files created *after* it starts watching — a
  file already sitting in `inbox/` before the watcher/app started won't be
  picked up automatically; process it manually (`python -m snapnotes.pipeline
  <path>`) or re-trigger it (move it out and back in).
- Anything else in `inbox/` (other file types, directories) is ignored.

## 2. Categories

Categories are **not** hardcoded anywhere. They're read live from Notion on
every screenshot, from every subpage or subdatabase directly under
`notion_home_url`:

- **Plain subpage** → a page category. Content gets appended as blocks to
  the page body.
- **Subdatabase** → a database category. Each screenshot becomes a new row
  (page) in that database, with typed properties filled in (see §4).

A category's description comes from the subpage/database's own body content
— a paragraph, or a "What this page is for:" callout block (including a
nested child block under it, not just the callout's own text). For a
database, its native "description" field is used instead.

**Per-category instructions**, read from a nested child block under that
same callout (same pattern as the description):

- `Format: <instructions>` — how to structure the entry instead of the
  generic table/bullets format (e.g. "toggle title = a short summary,
  inside: the full text in a code block"). See §3.
- `Include screenshot: yes` — embed the actual screenshot image as the
  first block inside the entry (only applies to format-instructed page
  categories, not databases). Uploaded straight to Notion via the File
  Upload API, not an external host.

To add a category: add a subpage or subdatabase under the home page in
Notion. Nothing else to do — the next screenshot processed will see it.

## 3. Classification + extraction

**Step 1 — classify (always runs).** One Gemini call (Flash-Lite): decide
which category the screenshot belongs to, extract the content, and format
it generically (table or bullets). See `gemini_client.py::build_prompt`.
Returns `ExtractionResult`:

- `matched_category` — name of the category, or `null` if nothing fits
- `title` — a specific, recognizable title (e.g. "Ollama AI Models
  (Granite, Mistral, Kimi)") — never a generic label ("X Overview") and
  never a bare unframed list of names. If several distinct items are
  covered, name the most notable few rather than picking just the first
  one or being vague.
- `content_type` — `"table"` or `"bullets"`, plus the matching fields
- `explanation` — always populated: what the screenshot is, and (when
  nothing matched) why it didn't fit any category
- `suggested_category` — populated when nothing matched; the closest guess

**This "closest match" behavior is validated (Phase 0, 4/4 pass) and must be
preserved.** Never replace it with a hard "none fit, discard" rejection —
the explanation + suggestion is what makes a `needs_review` item actionable
instead of a mystery file. This also means a category's own description on
its Notion page directly controls how strict/loose matching is — broadening
or narrowing that text (e.g. "any AI prompt" vs "prompts about agentic AI
specifically") changes classification behavior immediately, no code change.

**Step 2 — second, scoped call (only when needed):**

- **Database category matched** → `extract_database_fields` asks Gemini to
  fill in that specific database's actual properties (skipping read-only
  ones like `created_time`). Anchored to the step-1 title so the row title
  stays consistent. Single-value fields (`select`) are left empty rather
  than guessing when multiple distinct items don't share one value (e.g. 5
  different models with 5 different providers) — but multi-value/free-text
  fields (`multi_select`, `rich_text`) should still be filled in by
  aggregating across all the items, not left blank just because there are
  several.
- **Format-instructed page category matched** → `extract_formatted_entry`
  asks Gemini to structure the content per that category's `Format:`
  instruction (e.g. toggle + code block for verbatim prompts, toggle +
  bullets for portfolio observations) instead of the generic table/bullets.

## 4. Filing

- **Matched a database category** → create a new row via the File Upload
  API's data source (Notion's 2025-09-03 API split databases from "data
  sources" — row creation targets `data_source_id`, not `database_id`),
  properties from step 2, then append the generic table/bullets content
  (step 1) to that row's page body. Move the screenshot to
  `processed/<category>/`.
- **Matched a format-instructed page category** → append a toggle block
  (title from step 2, optionally the screenshot image first, then
  code/table/bullets) to the page. Move the screenshot to
  `processed/<category>/`.
- **Matched a plain page category** → append generic content (heading with
  title + timestamp, then table or bullets, then a divider) to the page.
  Move the screenshot to `processed/<category>/`.
- **Nothing matched** → move the screenshot to `needs_review/`. Log the
  explanation and suggested category so you can read them later without
  re-running anything.
- **Anything raised an exception** (network error, bad API response, etc.)
  → move the screenshot to `errors/`, log the full traceback. Never delete
  or silently drop a screenshot that failed to process — it's the only copy
  until it's safely in Notion. A failed *screenshot upload* specifically
  (e.g. still too large after compression) should never take the whole
  entry down with it — log it and save the entry without the image instead.

## 5. Failure handling

- **Gemini transient errors (429 per-minute, 5xx server errors)**:
  `gemini_client.py::_generate_with_retry` retries with exponential
  backoff + jitter, up to 3 retries, before giving up and letting it fall
  into `errors/`. A 429 that's specifically a per-day quota error (checked
  via the error message text) raises immediately instead of retrying —
  waiting a few seconds won't fix that, so there's no point burning
  retries or your remaining quota on it.
- **Notion API error** (bad page ID, integration not shared with the page,
  rate limit): falls into `errors/`. `scripts/setup_check.py` catches the
  common misconfigurations (missing token, home page not shared, no
  category subpages found, a database with no title property) before you
  ever get here.
- **Screenshot upload too large**: Notion's File Upload API caps a
  single-part upload at 5 MiB — a full-screen capture routinely exceeds
  that. `notion_client.py::_prepare_image_bytes` compresses to JPEG
  (quality first, then dimensions) before uploading; the upload itself is
  wrapped so a failure there never blocks the rest of the entry from saving.
- **macOS permission issues** (screenshot capture silently does nothing):
  not a code bug — Hammerspoon needs Screen Recording + Accessibility
  granted (it's the process that actually invokes `screencapture`).
  Terminal only needs Screen Recording if manually running `screencapture`
  from the command line — not required for the hotkey-driven pipeline.
- **Notifications not appearing**: `rumps.notification` doesn't reliably
  fire on modern macOS for an unbundled script, so `app.py` uses
  `terminal-notifier` instead (needs `brew install terminal-notifier` +
  one-time notification permission grant). Under `launchd`, PATH doesn't
  include `/opt/homebrew/bin`, so the binary is resolved via `shutil.which`
  with a Homebrew-path fallback rather than relying on bare PATH lookup.

## Known gaps (not yet built)

- No true review/confirmation gate before a Notion write commits (the
  lighter version - a "Added to X ✅" notification plus an Undo action in
  the menu bar's Recent Captures list - is built; a full pre-write
  approval gate was deliberately scoped out to keep the pipeline hands-off).
