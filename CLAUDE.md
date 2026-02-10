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

### Batched Publishing

Content mutations (create, edit, delete, toggle featured, image upload, bulk ops) commit locally without pushing. Changes accumulate until an admin/editor clicks "Publish to Site", which pushes all commits at once — triggering a single Railway deploy instead of one per edit.

**Git service functions:**
- `commit_locally(files, message, author)` — Stage + commit, no push
- `push_to_remote()` — Push all local commits to origin
- `get_unpushed_changes()` — List of `{sha, message, author, date}` for pending commits
- `has_unpushed_commits()` — Boolean check
- `ensure_repo()` — Fetches latest; rebases (preserving local commits) or hard-resets
- `commit_and_push()` — Legacy wrapper, calls commit_locally + push_to_remote

**UI:** Green publish bar in sidebar shows count of unpushed changes. JS polls `/api/pending-publish/` every 30 seconds and after any content-mutating fetch.

**Routes:**
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
- `chat/pending.html` / `chat/pending_detail.html` — Draft approval workflow
- `chat/media_library.html` — Image browser with upload
- `chat/content_health.html` — Health check dashboard

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
