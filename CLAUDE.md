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
