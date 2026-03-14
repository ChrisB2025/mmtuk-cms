# CLAUDE.md — MMTUK CMS + Website

## Project Overview

Django monolith serving both the MMTUK public website (mmtuk.org) and an AI-powered content management system. Content is stored in PostgreSQL (ORM) and page data in JSON files. Editors manage content via a chat interface powered by Claude.

- **Framework**: Django 5.x
- **Python**: 3.12+
- **Database**: SQLite (local), PostgreSQL (production via `DATABASE_URL`)
- **CSS**: Tailwind v4 (standalone CLI, no Node.js)
- **Deployment**: Railway.app via Dockerfile
- **Domain**: mmtuk.org (DNS via Cloudflare, proxied)

## Commands

```bash
python manage.py runserver                    # Dev server at localhost:8000
python manage.py migrate                     # Run database migrations
python manage.py collectstatic               # Collect static files
python manage.py import_markdown --source-dir PATH  # Import from Astro markdown (one-time migration)
./bin/tailwindcss.exe -i content/static/content/css/input.css -o content/static/content/css/output.css  # Rebuild CSS
./bin/tailwindcss.exe -i content/static/content/css/input.css -o content/static/content/css/output.css --watch  # Dev watch mode
```

## Architecture

### Apps

- **`content/`** — Public website: all page views, templates, static assets, models (Article, Briefing, News, Bio, LocalGroup, LocalEvent, LocalNews, EcosystemEntry)
- **`chat/`** — CMS: AI chat interface, content CRUD, media library, approvals, bug tracker
- **`accounts/`** — User profiles with roles (admin, editor, group_lead, contributor)

### URL Structure

- `/` — Public website (all content pages)
- `/cms/` — CMS interface (chat, content browser, pages, site-config, help, bugs)
- `/admin/` — Django admin panel

### Public Website Routes (`content/urls.py`)

| Route | View | Notes |
|-------|------|-------|
| `/` | Homepage | Hero slider, cards, testimonials |
| `/education/` | Education hub | Library, MMT intro, Core Insights + Objections accordions |
| `/education/<slug>/` | Article detail | 16 education articles (canonical URL) |
| `/research/` | Research hub | Policy areas, JG, ZIRP, briefings |
| `/research/briefings/` | Briefings index | Featured + grid |
| `/research/briefings/<slug>/` | Briefing detail | Source attribution, share buttons |
| `/research/job-guarantee/` | Job Guarantee | Policy paper with sidebar |
| `/community/` | Community hub | Local groups grid, events |
| `/about-us/` | About page | News, events, steering group, advisory board |
| `/donate/` | Donate page | Founder scheme, tiers, countdown |
| `/join/` | Join page | ActionNetwork form embed |
| `/founders/` | Founders directory | Not in nav, direct URL only |
| `/local-group/<slug>/` | Local group detail | Welcome, news, events, Discord |
| `/news/<slug>/` | News detail | Vimeo embed support |

**Redirects (301):**
- `/articles/<slug>/` → `/education/<slug>/` (legacy)
- `/education/articles/<slug>/` → `/education/<slug>/` (legacy)
- `/job-guarantee/` → `/research/job-guarantee/`
- `/library/` → `/education/`
- `/ecosystem/*` → `/`

### Content Models (`content/models.py`)

8 models: Article, Briefing, News, Bio, LocalGroup, LocalEvent, LocalNews, EcosystemEntry. All have `status` field (draft/published). Content stored as markdown in `body` field, rendered via `markdown` library with `extra` and `smarty` extensions.

### Page Data

Non-database page content lives in `content/data/pages/*.json` (home, donate, join, education, community, research, about-us, etc.). Loaded by `_load_page_data()` in views.

**Known limitation:** Page data JSON files are ephemeral on Railway — edits via CMS page editor are lost on redeploy. Accepted for now; page edits are rare.

### CMS Services (`chat/services/`)

- **`anthropic_service.py`** — Claude API integration (system prompt, message handling)
- **`content_service.py`** — ORM create/update/delete for content
- **`content_reader_service.py`** — ORM queries for listing/searching
- **`scraper_service.py`** — URL scraping for briefing imports
- **`image_service.py`** — Image processing (PNG→WebP, max 1200px)
- **`image_catalog.py`** — Media library hierarchical browsing
- **`field_mapping.py`** — camelCase↔snake_case field mapping + model resolution

### Static Files & Images

- **CSS**: Tailwind v4 standalone CLI (`./bin/tailwindcss.exe`), design tokens in `input.css`
- **Fonts**: Self-hosted Montserrat TTF (`content/static/content/fonts/`)
- **Images**: `content/static/content/images/` (bios, briefings, homepage, local-groups, news, pages, research)
- **Media uploads**: Persistent volume at `MEDIA_ROOT`
- **Serving**: WhiteNoise middleware for static files

### Design Tokens

- **Accent**: `#004537` (dark green)
- **Background**: `#fef9f1` (warm off-white)
- **Secondary**: `#e2cdaa` (warm tan)
- **Body text**: `#0c0800` (near-black with brown tint)
- **Body**: 17px, line-height 1.65, max-width 65ch
- **Cards**: 12px border-radius, hover translateY(-4px)

### User Roles & Permissions

| Role | Create | Edit | Delete | Approve | Publish |
|------|--------|------|--------|---------|---------|
| admin | all types | all | all | all | yes |
| editor | all types | all | all | all | yes |
| group_lead | local_event, local_news | own group | no | own group | no |
| contributor | articles, briefings, news | own content | no | no | no |

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DJANGO_SECRET_KEY` | prod | Django secret key |
| `DEBUG` | no | `True` for dev mode (default: `False`) |
| `ALLOWED_HOSTS` | prod | Comma-separated hostnames |
| `DATABASE_URL` | prod | PostgreSQL connection string (auto-set by Railway) |
| `ANTHROPIC_API_KEY` | yes | Claude API key |

### ALLOWED_HOSTS (Production)

`mmtuk-cms.up.railway.app,localhost,127.0.0.1,mmtuk.org,www.mmtuk.org`

`CSRF_TRUSTED_ORIGINS` auto-derives from `ALLOWED_HOSTS` (settings.py:150-152).

## Deployment

- **Dockerfile**: Python 3.12-slim, runs `collectstatic` in build phase
- **Startup** (Procfile CMD): `migrate → loaddata → setup_roles → setup_deployment_monitoring → setup_event_archival → warmup → gunicorn`
- **Static files**: WhiteNoise middleware
- **Database**: PostgreSQL via Railway plugin
- **Fixture**: `content/fixtures/initial_content.json` — 71 items (16 articles, 7 briefings, 5 news, 12 bios, 6 local groups, 3 events, 7 local news, 15 ecosystem entries)
- **Domain**: mmtuk.org + www.mmtuk.org via Railway custom domains with Cloudflare proxy

## Key Patterns

### Image path resolution

DB stores Astro-style paths: `/images/bios/Name.avif`. `_static_image_url()` converts to Django static URLs. Hero images use `{% static %}` directly. Fallback: `placeholder-image.svg`.

### Tailwind CSS rebuild

New utility classes require rebuilding `output.css`:
```bash
./bin/tailwindcss.exe -i content/static/content/css/input.css -o content/static/content/css/output.css
```

### Image optimization

PNG/JPEG → WebP (quality 82, method 6) for photos; WebP lossless for transparent. Max width 1200px.

## Migration History

This project was originally a standalone CMS that pushed markdown to a separate Astro static site repo. In March 2026, it was merged into a Django monolith serving both the CMS and public website directly. The old git publishing pipeline, Astro repo integration, and related services have been removed.

### Deprecated (removed in Phase 3 migration)
- `git_service.py` — Git operations for Astro repo
- `astro_validator.py` — Astro schema validation
- `railway_service.py` — Railway deployment monitoring
- `redirect_service.py` — Astro redirect generation
- Publish bar, review/publish workflow, pending publish API
