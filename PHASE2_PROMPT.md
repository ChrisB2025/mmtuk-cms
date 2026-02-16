# MMTUK CMS - Phase 2: Reliability & Validation

## Project Context

**Project:** MMTUK CMS - Django-based content management system for Astro 5.x static site
**Repository:** https://github.com/ChrisB2025/mmtuk-cms
**Production URL:** https://mmtuk-cms-production.up.railway.app
**Astro Site Repo:** https://github.com/ChrisB2025/MMTUK
**Audit Plan:** `C:\Users\chris\.claude\plans\abundant-marinating-quail.md`

## Stack

- **Backend:** Django 5.x + PostgreSQL + Redis + Django-Q2 (task queue)
- **Frontend:** Astro 5.x static site generator with Zod schema validation
- **Deployment:** Railway (auto-deploy on git push)
- **Content:** 8 collections (articles, news, events, briefings, podcasts, videos, partners, team_members)

## Phase 1 Completed ✅

### Part A: Orphaned Edit Processes (#1)
- ✅ **Discard Conversation** - Cancel work-in-progress, reset uncommitted changes
- ✅ **Delete Conversation** - Remove orphaned conversations from sidebar
- ✅ Soft git reset (`--soft HEAD~N`) for safe commit rollback
- ✅ User feedback via Django messages framework

### Part B: Build Failure Prevention (#2)
- ✅ **Pre-Commit Schema Validation** - All content validated against Astro Zod schemas
- ✅ **Railway Deployment Monitoring** - Track deployment status via GraphQL API
- ✅ **Deployment Status Widget** - Color-coded indicators in content browser
- ✅ **Automatic Monitoring Setup** - Django-Q schedule runs `monitor_deployments` every 5 minutes
- ✅ Schema fetching from Astro build artifacts (24-hour cache)

### Files Modified in Phase 1:
- `chat/models.py` - Added `discarded_at` field, `DeploymentLog` model
- `chat/views.py` - Discard/delete views, validation hooks, deployment tracking
- `chat/services/git_service.py` - `reset_unpushed_commits()` function
- `chat/services/astro_validator.py` - JSON Schema validation service
- `chat/services/railway_service.py` - Railway GraphQL API integration
- `chat/management/commands/monitor_deployments.py` - Polling command
- `chat/management/commands/setup_deployment_monitoring.py` - Schedule setup
- `chat/urls.py` - Discard/delete routes
- `chat/templates/` - UI for discard/delete buttons, deployment widget
- `Dockerfile` - Added `setup_deployment_monitoring` to startup sequence

## Phase 2: Reliability & Validation (CURRENT TASK)

**Goal:** Ensure all content types are correctly validated, implement lifecycle management, and harden validation patterns.

### Tasks to Complete:

#### #3: Schema Audit (Day 1 - ~6 hours)
**Problem:** Need to verify all 8 content types match Astro Zod schemas exactly.

**Tasks:**
1. Read `c:\Dev\Claude\MMTUK\src\content.config.ts` to understand canonical Zod schemas
2. Read `c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs` to verify JSON Schema generation
3. Compare CMS schema definitions (`c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py`) with Astro schemas
4. Identify any mismatches in:
   - Required vs optional fields
   - Field types (string, date, enum, etc.)
   - Default values
   - Enum options
5. Update `generate-schemas.mjs` if any schemas are missing or incorrect
6. Test validation with sample data for each content type
7. Document any schema evolution patterns (how to handle future changes)

**Deliverables:**
- Schema comparison report
- Updated `generate-schemas.mjs` if needed
- Updated CMS schema definitions if needed
- Test cases for all 8 content types

---

#### #6: Validation Hardening (Day 2 - ~6 hours)
**Problem:** Validation needs to be more robust and provide better error messages.

**Tasks:**
1. Review current validation implementation in `chat/services/astro_validator.py`
2. Add field-level validation helpers:
   - Date format validation (YYYY-MM-DD)
   - Slug format validation (lowercase-with-hyphens)
   - URL validation for links
   - Enum value validation
3. Improve error messages:
   - Show field path (e.g., "event.registrationLink")
   - Show expected vs actual value
   - Provide fix suggestions
4. Add validation test suite:
   - Test valid content passes
   - Test invalid content fails with clear errors
   - Test edge cases (null, empty string, whitespace)
5. Implement validation caching to avoid repeated schema fetches
6. Add validation metrics/logging for debugging

**Deliverables:**
- Enhanced validation error messages
- Field-level validation helpers
- Validation test suite
- Performance improvements

---

#### #4: Event Lifecycle (Days 3-4 - ~8 hours)
**Problem:** Past events remain in "Upcoming Events" list indefinitely.

**Solution:** Auto-archive events 7 days after they end.

**Tasks:**
1. Add `archived` boolean field to event schema (both Astro and CMS)
2. Create management command: `python manage.py archive_past_events`
   - Find events where `endDate < now() - 7 days`
   - Mark as archived
   - Optionally move to `/events/archive/` URL path
3. Update Astro site to filter archived events from upcoming list
4. Add Django-Q schedule to run archival daily
5. Create "Event Archive" page in CMS to view past events
6. Add "Unarchive" action for editors

**Deliverables:**
- `archive_past_events` management command
- Updated event schema with `archived` field
- Django-Q schedule for daily archival
- Event archive UI in CMS

---

#### #5: Removed Content SEO (Day 5 - ~6 hours)
**Problem:** Deleted content returns 404, harming SEO and user experience.

**Solution:** Generate 301 redirects for deleted content.

**Tasks:**
1. Track deleted content in `ContentAuditLog`:
   - Add `deleted_at` timestamp
   - Store original slug and content_type
2. Generate `_redirects` file (Netlify/Vercel format) or Astro redirects config:
   ```
   /articles/old-slug /articles/category 301
   /events/past-event /events 301
   ```
3. Add redirect generation to publish flow
4. Provide redirect suggestions in delete confirmation:
   - "Delete article: Where should readers be redirected?"
   - Default to content type index page
   - Allow custom redirect URL
5. Add redirect management UI:
   - List all redirects
   - Edit redirect target
   - Remove redirect (mark as intentional 404)

**Deliverables:**
- Redirect tracking in `ContentAuditLog`
- Redirect file generation
- Delete confirmation with redirect options
- Redirect management UI

---

## Key Files & Paths

### CMS (Django)
- **Models:** `c:\Dev\Claude\mmtuk-cms\chat\models.py`
- **Views:** `c:\Dev\Claude\mmtuk-cms\chat\views.py`
- **Schema Service:** `c:\Dev\Claude\mmtuk-cms\chat\services\astro_validator.py`
- **Templates:** `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\`
- **Management Commands:** `c:\Dev\Claude\mmtuk-cms\chat\management\commands\`

### Astro Site
- **Content Config:** `c:\Dev\Claude\MMTUK\src\content.config.ts`
- **Schema Generator:** `c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs`
- **Content Collections:** `c:\Dev\Claude\MMTUK\src\content\`

### Documentation
- **Audit Plan:** `C:\Users\chris\.claude\plans\abundant-marinating-quail.md`
- **Phase 1 Commit:** `84c2ae8` (Orphaned Edits & Build Failure Prevention)
- **Monitoring Commit:** `38873f0` (Automatic deployment monitoring setup)

## Important Patterns

### Git Operations
Always use `chat/services/git_service.py` functions with thread-safe `_git_lock`.

### Schema Validation
Use `chat/services/astro_validator.py::validate_against_astro_schema()` with fail-open pattern.

### Deployment Tracking
After `git push`, call `railway_service.get_latest_deployment()` and create `DeploymentLog`.

### Django-Q Schedules
Use `setup_deployment_monitoring.py` pattern for new scheduled tasks.

## Testing

- **Local Dev:** `python manage.py runserver` (port 8000)
- **Automated Tests:** `C:\Users\chris\.claude\skills\davila7-webapp-testing\test_mmtuk_cms.py`
- **Production:** https://mmtuk-cms-production.up.railway.app

## Current State

- ✅ Phase 1 deployed and tested
- ✅ Deployment monitoring active (checks every 5 minutes)
- ✅ Schema validation preventing build failures
- ⏳ Ready to start Phase 2

## Your Task

Please start with **#3: Schema Audit** as outlined above. Read the Astro schemas, compare with CMS schemas, identify any mismatches, and create a comprehensive comparison report.

Focus on ensuring 100% schema alignment between:
1. Astro `src/content.config.ts` (canonical source of truth)
2. `scripts/generate-schemas.mjs` (JSON Schema generator)
3. CMS validator (`chat/services/astro_validator.py`)

After completing the schema audit, we'll move to validation hardening (#6), then event lifecycle (#4), and finally removed content SEO (#5).

**Question:** Would you like to proceed with the schema audit (#3), or would you prefer to tackle a different Phase 2 task first?
