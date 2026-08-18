# SOP: Route a screenshot to Notion

This is the plain-language spec for what the pipeline does to one screenshot,
from the moment it lands in `inbox/` to the moment it's either filed in
Notion or flagged for review. The code in `snapnotes/` implements this; when
the code changes how it behaves, update this file to match.

## 1. What counts as a valid screenshot

- File extension is `.png`, `.jpg`, or `.jpeg`, dropped into `inbox/`.
- The watcher waits until the file's size stops changing across two checks
  before treating it as "arrived" — this avoids reading a screenshot mid-write.
- Anything else in `inbox/` (other file types, directories) is ignored.

## 2. Categories

Categories are **not** hardcoded anywhere. They're read live from Notion on
every screenshot: every subpage directly under `notion_home_url` is a
category, named after the subpage's title. A category's first paragraph
block (if it has one) becomes its description in the classification prompt.

To add a category: add a subpage under the home page in Notion. Nothing else
to do — the next screenshot processed will see it.

## 3. Classification + extraction

One Gemini call (Flash-Lite) does all of it: look at the screenshot, decide
which category it belongs to, extract the useful content, and format it.

Prompt shape (see `snapnotes/gemini_client.py::build_prompt`):

```
Here are my note categories:
<category name>: <category description>
...

Look at this screenshot and:
1. Decide which category it belongs to (or say none fit)
2. Extract the useful information
3. Format it as it should be appended to that note - use a
   table if it's comparative data, bullets otherwise
4. Keep it skimmable, not a wall of text

If nothing fits, explain what the screenshot is, why it doesn't fit any
category, and suggest the closest matching category.
```

Gemini returns structured JSON (`ExtractionResult` schema), not free text —
this is a Phase 1 upgrade over the Phase 0 manual-testing prompt, which
returned prose that had to be parsed. The fields:

- `matched_category` — name of the category, or `null` if nothing fits
- `title` — short title for this entry
- `content_type` — `"table"` or `"bullets"`
- `table_headers` / `table_rows` — populated when `content_type == "table"`
- `bullets` — populated when `content_type == "bullets"`
- `explanation` — always populated: what the screenshot is, and (when
  nothing matched) why it didn't fit any category
- `suggested_category` — populated when nothing matched; the closest guess

**This "closest match" behavior is validated (Phase 0, 4/4 pass) and must be
preserved.** Never replace it with a hard "none fit, discard" rejection —
the explanation + suggestion is what makes a `needs_review` item actionable
instead of a mystery file.

## 4. Filing

- **Matched a category** → append formatted content (heading with
  title + timestamp, then table or bullets, then a divider) to that
  category's Notion page. Move the screenshot to `processed/<category>/`.
- **Nothing matched** → move the screenshot to `needs_review/`. Log the
  explanation and suggested category so you can read them later without
  re-running anything.
- **Anything raised an exception** (network error, bad API response, etc.)
  → move the screenshot to `errors/`, log the full traceback. Never delete
  or silently drop a screenshot that failed to process — it's the only copy
  until it's safely in Notion.

## 5. Failure handling

- **Gemini 429 (rate limited)**: not yet distinguished from other errors —
  currently falls into the generic `errors/` path. When this is hit for
  real: check the response for whether it's a per-minute or per-day limit.
  If per-minute, add exponential backoff with jitter and retry. If per-day,
  stop processing and surface it — don't silently retry all day on a free
  tier.
- **Notion API error** (bad page ID, integration not shared with the page,
  rate limit): falls into `errors/`. `scripts/setup_check.py` catches the
  common misconfigurations (missing token, home page not shared, no
  category subpages found) before you ever get here.
- **macOS permission issues** (screenshot capture silently does nothing):
  not a code bug — check Hammerspoon/Terminal have Screen Recording and
  Accessibility granted in System Settings before debugging the pipeline.

## Known gaps (not yet built)

- No retry/backoff on Gemini rate limits yet (see above).
- No review/confirmation notification before a Notion write commits — this
  is a deliberate Phase 2 deferral, not an oversight. Don't add it without
  checking first.
