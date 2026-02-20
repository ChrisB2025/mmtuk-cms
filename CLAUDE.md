# CLAUDE.md — MMTUK CMS

## Project Overview

Django-based content management system for the MMTUK static site (mmtuk.org). Editors create/edit content via an AI chat interface (Claude), which generates markdown files committed to the MMTUK site repo on GitHub. Railway auto-deploys the site from that repo.

- **Framework**: Django 5.x
- **Python**: 3.11+
- **Database**: SQLite (local), PostgreSQL (production via `DATABASE_URL`)
- **Deployment**: Railway.app via Dockerfile

## Commands

```bash
python manage.py runserver        # Dev server at localhost:8000
python manage.py migrate          # Run database migrations
python manage.py createsuperuser  # Create admin user
python manage.py collectstatic    # Collect static files
```

## Architecture

### Apps

- **`chat/`** — Main app: conversations, content CRUD, media library, approvals
- **`accounts/`** — User profiles with roles (admin, editor, group_lead, contributor)
- **`content_schema/`** — Zod-like content type definitions (articles, briefings, news, etc.)

### Key Services (`chat/services/`)

- **`git_service.py`** — Git operations for the MMTUK site repo
- **`anthropic_service.py`** — Claude API integration (system prompt, message handling)
- **`content_service.py`** — Markdown generation from frontmatter + body
- **`content_reader_service.py`** — Read/list/search content from repo clone
- **`scraper_service.py`** — URL scraping for briefing imports
- **`image_service.py`** — Image processing and conversion
- **`pdf_service.py`** — PDF text/image extraction
- **`image_catalog.py`** — Categorises images by site section/subsection for hierarchical media library browsing; groups Webflow responsive variants (`-p-500`, `-p-800`, etc.) under base images

### Batched Publishing

Content mutations (create, edit, delete, toggle featured, image upload, bulk ops) commit locally without pushing. Changes accumulate until an admin/editor clicks "Publish to Site", which pushes all commits at once — triggering a single Railway deploy instead of one per edit.

**Git service functions:**
- `commit_locally(files, message, author)` — Stage + commit, no push
- `push_to_remote()` — Push all local commits to origin
- `get_unpushed_changes()` — List of `{sha, message, author, date}` for pending commits
- `has_unpushed_commits()` — Boolean check
- `ensure_repo()` — Fetches latest; rebases (preserving local commits) or hard-resets
- `commit_and_push()` — Legacy wrapper, calls commit_locally + push_to_remote

**UI:** Green publish bar in sidebar links to the Review & Publish page (`/review/`). JS polls `/api/pending-publish/` every 30 seconds and after any content-mutating fetch.

**Routes:**
- `GET /review/` — Review & Publish dashboard: shows unpushed commits, pending drafts, recent audit log
- `POST /publish/` — Push all local commits (admin/editor only)
- `GET /api/pending-publish/` — JSON `{count, commits: [...]}`

### User Roles & Permissions

| Role | Create | Edit | Delete | Approve | Publish |
|------|--------|------|--------|---------|---------|
| admin | all types | all | all | all | yes |
| editor | all types | all | all | all | yes |
| group_lead | local_event, local_news | own group | no | own group | no |
| contributor | articles, briefings, news | own content | no | no | no |

### Content Types

Defined in `content_schema/schemas.py`. Each type has a name, directory, file pattern, route, and field schema:

- **articles** — `src/content/articles/`
- **briefings** — `src/content/briefings/`
- **news** — `src/content/news/`
- **bios** — `src/content/bios/`
- **ecosystem** — `src/content/ecosystem/`
- **localGroups** — `src/content/localGroups/`
- **localEvents** — `src/content/localEvents/`
- **localNews** — `src/content/localNews/`

### Templates

- `chat/base.html` — Layout with sidebar (tabs, publish bar, nav, footer)
- `chat/index.html` — Chat interface with suggested actions
- `chat/content_browser.html` — Card grid with filters, search, bulk ops
- `chat/content_detail.html` — Single content view with quick edit
- `chat/review_changes.html` — Review & Publish dashboard (unpushed commits, pending drafts, audit log)
- `chat/pending.html` / `chat/pending_detail.html` — Draft approval workflow
- `chat/media_library.html` — Image browser with hierarchical section view (default) and flat view toggle
- `chat/content_health.html` — Health check dashboard

### Media Library — Hierarchical Browsing

The media library (`/media/`) displays images organised by site section rather than a flat grid. This is powered by `chat/services/image_catalog.py`.

**Section view** (default): Images are categorised into collapsible sections (Research, Education, Community, About Us, Join, Donate, Homepage, Shared) with subsections (Hero, Cards, Team Photos, etc.). Categorisation uses directory paths (`bios/` → About Us, `local-groups/` → Community) and filename pattern matching. Webflow responsive variants (`-p-500`, `-p-800`, `-p-1080`, etc.) are grouped under their base image with an expandable "N sizes" indicator.

**Flat view** (`?view=flat`): The original flat grid, accessible via a toggle button in the header.

**Adding new image categories**: Edit `SITE_SECTIONS` in `image_catalog.py`. Each section has subsections with either `'directory'` (matches images in that subdirectory) or `'patterns'` (case-insensitive substring matches against the base filename). Unmatched images fall through to "Shared / Site Assets / Other".

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | prod | Django secret key |
| `DEBUG` | no | `True` for dev mode (default: `False`) |
| `ALLOWED_HOSTS` | prod | Comma-separated hostnames |
| `DATABASE_URL` | prod | PostgreSQL connection string (auto-set by Railway) |
| `ANTHROPIC_API_KEY` | yes | Claude API key |
| `GITHUB_TOKEN` | yes | GitHub PAT for pushing to MMTUK repo |
| `GITHUB_REPO` | no | Target repo (default: `ChrisB2025/MMTUK`) |
| `GITHUB_BRANCH` | no | Target branch (default: `optimize-deploy`) |
| `ADMIN_USERNAME` | no | Auto-created admin username |
| `ADMIN_PASSWORD` | no | Auto-created admin password |

### DEBUG Mode Behavior

When `DEBUG=True`:
- Git operations are skipped — files write to `output/` directory instead
- `commit_locally()` returns `'debug-no-push'`
- `get_unpushed_changes()` returns `[]`
- Content reads fall back to `output/` if not found in repo clone

## Deployment

- **Dockerfile**: Multi-stage build — `node:20-alpine` not needed, uses `python:3.11-slim`
- **`railway.toml`**: Sets builder to dockerfile, healthcheck on `/health/`
- **Static files**: Served via WhiteNoise middleware
- **Database**: PostgreSQL via Railway plugin (auto-sets `DATABASE_URL`)

## Common Patterns

### Adding a New Content Mutation

1. Write file to repo with `write_file_to_repo()` (or `write_file_to_output()` in DEBUG)
2. Commit with `commit_locally(files, message, author_name)` — NOT `commit_and_push()`
3. Call `_log_audit()` for the audit trail
4. Call `invalidate_cache()` to refresh content listings

### Deleting Content

1. `ensure_repo()` to get latest
2. `delete_file_from_repo(file_path)` to remove the file
3. `commit_locally([file_path], message, author)` — handles staging the removal automatically
4. Log + invalidate cache

## Phase 2: Reliability & Validation

### Schema Audit (Task #3) ✅ Complete

**Problem:** CMS schemas were out of sync with Astro Zod schemas, causing validation failures for valid content.

**Solution:**
- Audited all 8 content types against canonical Astro schemas
- Fixed 6 field optionality mismatches (briefing, news, ecosystem)
- Added missing `local_group` content type
- Created test suite with 27 tests (100% passing)

**Files:**
- `content_schema/schemas.py` — Fixed optionality, added local_group
- `SCHEMA_AUDIT_REPORT.md` — Comprehensive audit documentation
- `test_schema_validation.py` — 27 tests for schema validation

### Validation Hardening (Task #6) ✅ Complete

**Problem:** Validation errors were generic and unhelpful, making debugging difficult.

**Solution:**
- Created field-level validation helpers with detailed error messages
- Enhanced error formatting with fix suggestions
- Added validation metrics tracking
- Created comprehensive test suite (40 tests, 100% passing)

**New Services:**
- `chat/services/validation_helpers.py` — Field validators (date, slug, URL, enum, length)
- `chat/management/commands/validation_metrics.py` — View validation health

**Enhanced Services:**
- `chat/services/astro_validator.py` — Enhanced error messages, metrics tracking

**Error Message Example:**
```
❌ Validation Error:

**slug**: Invalid slug: contains uppercase letters, contains spaces
  Actual value: 'My Article Title'
  Expected format: lowercase-with-hyphens (e.g., 'my-article-slug')
  💡 Convert to lowercase, replace spaces with hyphens (e.g., 'my-article-title')
```

**Validation Metrics:**
```bash
python manage.py validation_metrics  # View success rates per content type
```

**Documentation:**
- `VALIDATION_HARDENING.md` — Complete API reference and usage guide
- `VALIDATION_FLOW.md` — Architecture diagrams and flow documentation
- `PHASE2_TASK6_SUMMARY.md` — Executive summary

### Event Lifecycle (Task #4) ✅ Complete

**Problem:** Past events remained in "Upcoming Events" list indefinitely.

**Solution:**
- Added `endDate` and `archived` fields to event schema
- Created management command to auto-archive events 7+ days after end date
- Set up Django-Q daily schedule for automatic archival
- Built Event Archive page (/events/archive/) to view archived events
- Added unarchive action for admins/editors

**New Management Commands:**
- `chat/management/commands/archive_past_events.py` — Archive past events
- `chat/management/commands/setup_event_archival.py` — Set up daily schedule

**New Pages:**
- `/events/archive/` — View and manage archived events

**Usage:**
```bash
# Archive past events (runs daily via Django-Q)
python manage.py archive_past_events

# Preview what would be archived
python manage.py archive_past_events --dry-run

# Set up daily archival schedule
python manage.py setup_event_archival
```

**Event Lifecycle:**
1. Event created (archived: false)
2. Event ends (endDate passes)
3. Wait 7 days grace period
4. Daily job auto-archives event (archived: true)
5. Event hidden from upcoming list, visible in archive
6. Admin/editor can unarchive if needed

**Documentation:**
- `PHASE2_TASK4_SUMMARY.md` — Complete implementation guide

### Removed Content SEO (Task #5) ✅ Complete

**Problem:** Deleted content returns 404, harming SEO and user experience.

**Solution:**
- Track deleted content in ContentAuditLog with redirect_target field
- Generate Astro redirects config (301 redirects) for deleted content
- Integrate redirect generation into publish flow
- Provide redirect suggestions in delete confirmation
- Build redirect management UI for viewing/editing redirects

**New Services:**
- `chat/services/redirect_service.py` — Redirect generation and validation

**New Pages:**
- `/redirects/` — View and manage redirects (admin/editor only)

**Enhanced Models:**
- `ContentAuditLog` — Added `deleted_at` and `redirect_target` fields

**Enhanced Views:**
- `delete_content` — Prompts for redirect target before deletion
- `publish_changes` — Auto-generates redirects.config.mjs before push

**Usage:**
```bash
# View all redirects
Navigate to: /redirects/

# Generate redirects manually (via Django shell)
python manage.py shell
>>> from chat.services.redirect_service import write_redirects_to_repo
>>> write_redirects_to_repo()

# Run tests
python -m pytest chat/tests/test_redirects.py -v
```

**Redirect Workflow:**
1. User deletes content via CMS
2. Delete modal prompts for redirect target (or intentional 404)
3. ContentAuditLog entry created with deleted_at and redirect_target
4. On publish, redirects.config.mjs generated and committed
5. Astro site deployed with 301 redirects active
6. Old URLs redirect to specified targets (SEO preserved)

**Astro Integration:**
```javascript
// astro.config.mjs
import autoRedirects from './redirects.config.mjs';

export default defineConfig({
  redirects: {
    ...autoRedirects,  // Auto-generated from CMS
    // Manual redirects below (take precedence)
  }
});
```

**Test Suite:**
- 19 tests covering redirect tracking, generation, validation, and management
- All tests passing (100%)

**Documentation:**
- `PHASE2_TASK5_SUMMARY.md` — Complete implementation guide
- `pytest.ini` — Pytest configuration for Django tests

---

## Session: Chat Reliability Fixes (2026-02-19)

### Problem Summary

The AI chat interface had two persistent issues:
1. **Empty/invisible AI chat bubbles** on page reload
2. **"Network error"** on Substack URL import and article confirmation

Both were diagnosed and fixed across multiple commits.

---

### Fix 1 — Empty AI Chat Bubbles (commit `4f06e71`)

**Root cause:** `{{ msg.content|escapejs|safe }}` was used in the template without wrapping
in JS string quotes. `escapejs` escapes special characters but does NOT add the surrounding
`"..."`. The resulting `marked.parse(Hello world)` threw a syntax error silently.

**Fixes applied:**
- Added `"..."` quotes around `escapejs` output in `chat/templates/chat/index.html`
- Pinned marked.js to specific version (`@15.0.12`) to avoid CDN version drift
- Added try/catch around `marked.parse()` with plaintext fallback
- Added `display_text` fallback in `views.py` to prevent raw JSON leaking to the client

**Key lesson:** Django's `escapejs` escapes string *contents* only. You must add the
surrounding `"..."` yourself: `"{{ value|escapejs }}"`.

---

### Fix 2 — Django 5 Logout 405 Error (commit `5f0c422`)

**Root cause:** Django 5.x changed `LogoutView` to require POST. The sidebar had an `<a href="{% url 'logout' %}">` anchor which issues a GET request.

**Fix:** Replaced the anchor with a `<form method="post">` containing a `{% csrf_token %}` and a styled `<button type="submit">`. Added button-reset CSS to `style.css`.

**Key lesson:** Django 5 requires POST for logout. Never use an anchor tag for logout.

---

### Fix 3 — Double Claude API Calls (commit `d95695c`)

**Root cause:** `_handle_scrape_action()`, `_handle_read_action()`, and `_handle_list_action()` each made a second `call_claude()` call after the initial one in `send_message`. Every scrape/read/list request was calling the Claude API twice — doubling latency.

**Fix:** Each handler now builds and returns a formatted response directly without
re-calling Claude. The scraped/read/listed data is formatted into markdown and returned as a string.

**Key lesson:** Never call `call_claude()` inside action handlers. Build the response directly from the data.

---

### Fix 4 — Git Fetch on Read Path (commit `8da5147`)

**Root cause:** Every `send_message` call triggered `build_system_prompt()` → `get_content_stats()` → `list_content()` → `_ensure_repo_available()` → `ensure_repo()` → `origin.fetch(kill_after_timeout=30)`. This added 10-30s to every cold-cache request **outside** any try/except, so Railway's proxy timeout cut the connection and the JS catch block showed "Network error".

**Fix:**
- `_ensure_repo_available()` in `content_reader_service.py` now returns immediately if the
  clone directory exists (no network call). Only calls `ensure_repo()` for the initial clone.
- `build_system_prompt()` moved inside the try/except block that wraps `call_claude()`,
  with a timing log.

**Key lesson:** The read path (`list_content`, `get_content_stats`) must never trigger git fetch. Only the write path should fetch. The warmup command pre-clones the repo so reads always find the directory.

---

### Fix 5 — Git Fetch on Write Path (commit `d4ad1ec`)

**Root cause:** `_handle_content_action()` in `views.py` called `ensure_repo()` before writing, which triggered `origin.fetch(kill_after_timeout=30)` on every gunicorn worker's first request. Combined with Claude API time (20-60s), requests exceeded Railway/Cloudflare's ~100s proxy timeout.

**Fix:** Added `prepare_repo_for_write()` to `git_service.py`. This function:
- Updates the remote URL (token refresh, instant)
- Runs `git checkout branch` (local, instant)
- Does **not** fetch from remote

`push_to_remote()` already handles non-fast-forward pushes via `git pull --rebase` retry, so no pre-fetch is needed.

**Key lesson:** Distinguish three git operations by cost:
- `git checkout` / `set_url` → instant, safe anywhere
- `origin.fetch()` → 5-30s network call, only call from the **warmup command** (deploy startup)
- `git push` → 1-5s, handles divergence via rebase retry

---

### Fix 6 — Scrape Happens After Claude (commit `408647f`)

**Root cause:** When a user sent a Substack URL, Claude would ask "import or write original?" (fast). On the next message ("yes import"), Claude responded (20-60s) and **then** Django called `scrape_url()` (5-30s). Total: 25-90s → hits Railway/Cloudflare ~100s proxy timeout → `TypeError: Failed to fetch` in JS → "Network error".

**Fix:** Added `_pre_scrape_substack()` helper in `views.py`. Before calling Claude, the function:
1. Detects any `substack.com` URL in the user message via regex
2. Calls `scrape_url()` (5-30s) **before** the Claude API call
3. Injects the scraped content as a `[SYSTEM: The URL X was scraped...]` message into the conversation DB

Claude then sees the full article in context and responds with the preview directly. No `scrape` action block is needed, eliminating the post-Claude scrape delay.

**Bonus UX improvement:** The "import or write original?" clarifying question is eliminated. The article preview appears immediately when the user sends a Substack URL.

**System prompt updated** to tell Claude: "If you see `[SYSTEM: The URL X was scraped...]` already in the conversation, do NOT emit a scrape action — the data is already available."

**Key lesson:** When a request involves two slow operations (Claude API + scrape), split them so they don't compound in a single request. Move the scrape **before** Claude so the total time is `max(scrape, Claude)` rather than `scrape + Claude`.

---

### Railway/Cloudflare Proxy Timeout — Empirical Finding

Railway uses Cloudflare, which has a **~100s hard timeout** on upstream HTTP connections. This is the actual constraint, not gunicorn's `--timeout 300`.

**Budget per request:**
- Claude API: 20-60s (typical), up to 120s (configured timeout)
- Scrape URL: 5-30s
- Git operations: only `warmup` (deploy) should call `ensure_repo()`
- Schema validation: <3s (cached in Redis/LocMemCache) or up to 24s (cold)

**Rule of thumb:** Any single HTTP request must complete within ~80s to be safe (leaving buffer before the 100s cut).

---

### Warmup Command (`chat/management/commands/warmup.py`)

Runs at deploy startup (in Dockerfile CMD). Pre-clones the MMTUK site repo to disk so the first user request doesn't need to clone or fetch. Without warmup, the first request to each gunicorn worker would hit `origin.fetch()` and potentially timeout.

---

### Architecture Notes (Updated)

- **`_ensure_repo_available()`** (`content_reader_service.py`) — Read-only check: returns immediately if clone dir exists. Never fetches.
- **`prepare_repo_for_write()`** (`git_service.py`) — Pre-write setup: updates remote URL + `git checkout`. Never fetches.
- **`ensure_repo()`** (`git_service.py`) — Full sync: fetches + rebases/resets. Only called by warmup command and initial clone.
- **`push_to_remote()`** (`git_service.py`) — Handles push with automatic rebase retry on non-fast-forward.
- **`_pre_scrape_url()`** (`views.py`) — Eagerly scrapes any URL (not just Substack) before Claude is called, so scraped content is in context. Renamed from `_pre_scrape_substack()`.

---

## Session: Scraper Quality, Chat UX, and Briefing Fixes (2026-02-20)

### General URL Scraping Improvements

**Problem:** `scrape_general_url()` was significantly worse than `scrape_substack()` — no figure preprocessing, no heading enforcement, no CTA/navigation cleanup. Non-Substack URLs went through Claude (slower) instead of the fast direct-scrape path.

**Fixes applied (`chat/services/scraper_service.py`):**
- Extended `scrape_general_url()` with `_preprocess_figures()`, `_enforce_h2_only()`, `_strip_title_heading()`, CTA/nav cleanup, and fallback image extraction from first `<img>` when og:image missing
- `_enforce_h2_only()` now handles H1→H2 (not just H3→H2)
- New `_strip_title_heading()` helper removes first heading when it duplicates the title
- Shared `_CTA_PATTERNS` list (navigation links like "← Back to Articles" stripped)
- New `_strip_thumbnail_from_body()` strips the thumbnail image from body markdown to avoid duplication with frontmatter

**Fixes applied (`chat/views.py`):**
- Added `_GENERAL_URL_RE` — Step 2 in `send_message()` now matches ANY URL (not just Substack)
- `_pre_scrape_substack()` renamed to `_pre_scrape_url()` with general URL regex
- Failed scrapes fall through to Claude (Step 3) instead of returning an error
- `_direct_briefing_from_scraped()`: `author` field uses scraped author name (not hardcoded 'MMTUK'); `sourceAuthor` only set when non-empty

### Chat Home Page Suggested Actions

**Problem:** "Import Briefing from URL" and "Write New Article" were confusingly similar. No button for "Create a Briefing" from scratch. "Import" message still referenced "Substack URL".

**Fix (`chat/views.py` `SUGGESTED_ACTIONS`):**
- "Import Briefing from URL" → **"Add Briefing"** (covers URL import + writing from scratch)
- "Add News Item" → **"Add News"**
- "Write New Article" → **"Write Article"**
- "Upload a PDF" → **"Upload Document"** (also handles DOCX)
- "Add Team Member Bio" → **"Add Team Member"**
- Reordered: briefing first (most common workflow)

### Scrape Preview Markdown Rendering

**Problem:** Preview included first 300 chars of body_markdown. When body started with `![alt](very-long-S3-url...)`, truncation broke the markdown mid-URL, causing raw text to render instead of formatted content. Also showed "By Unknown author".

**Fix (`chat/views.py` `_format_scrape_preview()`):**
- `_IMAGE_MD_RE` strips `![...](...)` image markdown before taking the 300-char slice
- `_BARE_URL_RE` strips bare URLs on their own lines
- Author line omitted when no author found (no more "By Unknown author")

**Fix (`chat/static/chat/style.css`):**
- Added `.markdown-body img` rules (max-width: 100%, border-radius)
- Added `.markdown-body a` rules (teal color, underline, hover state)

### Delete Modal Overlay

**Problem:** Delete confirmation modal backdrop was transparent — page content visible behind it.

**Fix (`chat/static/chat/style.css`):**
- Modal overlay uses explicit `width: 100vw; height: 100vh` instead of `inset: 0`
- Increased background opacity to `rgba(0, 0, 0, 0.6)`
- Hardcoded `z-index: 9000` (was CSS variable `var(--z-modal-backdrop)`)
- Modal in `{% block modals %}` outside `.app-layout` (prevents overflow clipping)

### Astro Site Fixes (MMTUK repo)

**Attribution box (`[slug].astro`):**
- "In Response To" → **"Originally Published"**
- Default fallback: "View original article"
- Separator logic fixed for missing sourceAuthor

**Share buttons (`[slug].astro` + `BaseLayout.astro`):**
- Copy button was destroying SVG icon (used `innerText` instead of `innerHTML`)
- Fallback `window.open(shareUrl)` removed — was opening page in new tab instead of copying
- Now saves/restores `icon.innerHTML` to preserve SVG icon after "Copied" feedback

---

## Session: Image Compression, Template Cleanup, Validation Fix (2026-02-20)

### Image Pipeline: PNG to WebP

**Problem:** All scraped and uploaded images saved as PNG (lossless). Briefing thumbnails were 1.8 MB each. Event images up to 429 KB.

**Fix (`chat/services/image_service.py`):**
- `convert_to_png()` renamed to `optimize_image()` — now saves as WebP (quality 82, method 6) for photos, WebP lossless for transparent images
- `process_image()` returns `.webp` filenames instead of `.png`
- Backward-compat alias `convert_to_png = optimize_image` retained
- Upload handler (`views.py`) now also applies `max_width=1200` (previously missing for manual uploads)

**Updated references:**
- `chat/views.py`: hardcoded `.png` paths → `.webp` in `_direct_briefing_from_scraped()` and `upload_image()`
- `chat/services/content_service.py`: `get_image_path()` default extension `'png'` → `'webp'`
- `chat/services/anthropic_service.py`: Claude prompt examples updated to `.webp`
- `chat/management/commands/compress_images.py`: Rewritten — converts existing PNGs/JPEGs to WebP, renames files, updates frontmatter refs in `.md` files. Runs automatically on deploy via Dockerfile CMD.

**Result:** 35 images converted, 76% total savings. Briefing thumbnails now ~100-150 KB.

### Briefing/Article Template Cleanup

**Problem:** Briefing pages showed forced "Summary" + "Analysis" headings. Articles showed "Executive Summary" + "Content". These were legacy Webflow structure that duplicated content and imposed rigid formatting.

**Fix (Astro repo):**
- `[slug].astro` (briefings): Removed Summary block and "Analysis" label entirely
- `[slug].astro` (articles): Removed "Executive Summary" block and "Content" label
- Article body now flows naturally from title/date without imposed structure
- `summary` field preserved in schema for SEO meta and listing page previews

### pubDate Validation Fix

**Problem:** CMS couldn't edit briefings with unquoted `pubDate` in YAML. PyYAML parses bare ISO dates as Python `datetime` objects, but the validator expected strings.

**Fix (`chat/services/content_service.py` `sanitize_frontmatter()`):**
- Converts `datetime`/`date` objects to strings using `format_date()` before validation runs
- This runs in the sanitize step, before `validate_frontmatter()` is called

### Featured Briefing

Changed featured briefing from "On The Nature of Money" to "Shadows on the Wall" via frontmatter `featured: true/false` toggle in the briefing `.md` files.
