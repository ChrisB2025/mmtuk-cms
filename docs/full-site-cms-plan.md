# Plan: Full Website Management via MMTUK CMS

## Context
The MMTUK CMS currently manages content collections (articles, briefings, news, bios, etc.) but all static pages — home, about-us, education, research, community, donate, join, job-guarantee, privacy-policy, and others — are hard-coded Astro files. Editing them requires touching source code directly.

This plan extends the CMS to manage the entire MMTUK website: all static page content, site-wide configuration (Discord URL, Stripe links, deadlines), and new page creation from templates. It preserves the existing git-commit-then-publish workflow and RBAC system, extending both for page-level and field-level access control.

---

## Architecture Overview

### Core Design Decisions

**1. Data Layer: JSON files in `src/data/pages/`**
Astro 5.x / Vite natively imports `.json` files with no configuration. JSON is language-neutral so the Python CMS can write it trivially. Content collections are for list-type content (many articles); single-instance page data is a better fit for plain JSON.

```
src/data/pages/
  home.json, about-us.json, education.json, research.json,
  community.json, donate.json, join.json, job-guarantee.json,
  privacy-policy.json, terms-of-engagement.json, cookie-preferences.json
  site-config.json   ← site-wide settings (Discord URL, Stripe, etc.)
  manifest.json      ← page registry (avoids modifying Python source at runtime)
```

**2. Astro pages become thin templates**
Each `.astro` page adds one import line and replaces hard-coded values with `{data.field}`. Complex data types (accordion arrays, slider items, testimonials) are handled with `.map()`. Rendering logic (HTML structure, JavaScript) stays in the .astro file. Dynamic sections (getCollection calls) are unchanged.

**3. `manifest.json` as the page registry**
Rather than hard-coding page keys in Python source (which would need modification when new pages are added), a `manifest.json` in the Astro repo lists all managed pages. The CMS reads this file to know which pages exist. New page creation updates the manifest and commits it alongside the new data file and .astro template.

**4. Parallel editing routes: Form editor + Chat**
Static pages have structured data (not freeform prose), so a form-based section editor is the primary editing UI. The AI chat interface is extended to also handle page edits as a secondary route (useful for rewrites or changes spanning multiple sections). This mirrors how the existing CMS works: both the content browser (form-like) and chat are available for articles.

**5. `site-config.json` is the single source for sensitive settings**
Stripe links, Discord URL, and Action Network form IDs live only in `site-config.json`. The donate, community, join, and founders Astro pages import them from there. This means updating a Stripe link is one file change, not editing multiple pages.

---

## Static Page Content Inventory

| Page | Complexity | Editable Sections | Admin-only Fields |
|------|-----------|-------------------|-------------------|
| `home` | High | Hero, 3 slides, section headings, 2 research cards, 2 education cards, 3 community cards, 3 testimonials, contact email | — |
| `about-us` | Medium | Hero heading/image, section headings, steering group sort order | — |
| `education` | High | Hero, "What is MMT?" (2 para), 7 core insight accordions, 12 objection accordions, advisory services | — |
| `research` | Medium | Hero, 2 policy area sections (JG + ZIRP: heading, description, 3 feature points each), 5 approach cards | — |
| `community` | Low | Hero, Discord section heading/description | `discord_url` (in site-config) |
| `donate` | Medium | Hero, founder scheme heading/description, milestone text, deadline date, 3 tier headings/amounts | `stripe_links` (in site-config) |
| `join` | Low | Hero, intro text, 6 benefits list items | `action_network_form_id` (in site-config) |
| `job-guarantee` | Medium | Page title, publication date, 3 contributors (name + photo), Vimeo video ID, full policy body (markdown) | — |
| `privacy-policy` | Simple | Markdown body, last updated date | — |
| `terms-of-engagement` | Simple | Markdown body, last updated date | — |
| `cookie-preferences` | Simple | Markdown body | — |
| `site-config` | n/a | Announcement bar, contact email | Discord URL, all Stripe links, Action Network form ID |

---

## RBAC Matrix

| What | Admin | Editor | Group Lead | Contributor |
|------|-------|--------|------------|-------------|
| Edit any static page (text sections) | ✅ | ✅ | ❌ | ❌ |
| Edit admin-only fields (Stripe, Discord, embed IDs) | ✅ | ❌ | ❌ | ❌ |
| Edit site-config (non-sensitive) | ✅ | ✅ | ❌ | ❌ |
| Edit site-config (sensitive fields) | ✅ | ❌ | ❌ | ❌ |
| Create new page from template | ✅ | ❌ | ❌ | ❌ |
| Delete / retire a page | ✅ | ❌ | ❌ | ❌ |
| Upload images to page directories | ✅ | ✅ | ❌ | ❌ |

**Key principle**: There is no draft/approval queue for page edits. Editors publish directly (same as `can_publish_directly()` for their permitted content types). Pages are too tightly coupled to live UX to benefit from a pending queue — an editor correcting a typo on the home page shouldn't wait for admin approval.

**Admin-only sections** are enforced at two levels:
1. Not rendered in the form editor for non-admin users
2. Validated server-side in the page API view before any write

---

## Implementation Phases

### Phase 1 — Foundation (simple pages + data layer)

**Goal**: Prove the end-to-end pipeline works without disrupting anything.

**Astro changes:**
- Create `src/data/pages/` directory
- Write `privacy-policy.json`, `terms-of-engagement.json`, `cookie-preferences.json` (each: `{title, last_updated, body}` where body is markdown string)
- Modify those 3 `.astro` pages to import their JSON and render body with `set:html={marked(data.body)}`
- Add `marked` as a dependency (or use Astro's built-in markdown rendering)
- Write `manifest.json` listing these 3 pages initially

**CMS changes:**
- Create `chat/services/page_service.py` with `read_page_data`, `write_page_data`, `apply_page_patch`, `_deep_merge`
- Add `PAGE_TYPES` dict to `content_schema/schemas.py` (alongside existing `CONTENT_TYPES`), starting with the 3 simple pages
- Add `/pages/` URL → `page_manager` view (admin/editor only, read-only display initially)
- Add "Pages" nav entry to `base.html` (visible to admin and editor only)

**Verification**: Build the Astro site locally — privacy policy renders from JSON. Check no regressions.

---

### Phase 2 — Site Config (admin-protected settings)

**Goal**: Remove all hard-coded external service URLs from .astro source code.

**Astro changes:**
- Write `src/data/pages/site-config.json` with Discord URL, Stripe links, Action Network form ID, founder milestone settings, announcement bar
- Update `community.astro` to import Discord URL from site-config
- Update `donate.astro` to import Stripe links and milestone/deadline settings from site-config
- Update `join.astro` to import Action Network form ID from site-config
- Update `founders.astro` to import Discord URL from site-config
- Update `BaseLayout.astro` to conditionally render announcement bar from site-config

**CMS changes:**
- Add `site_config` to `PAGE_TYPES` with `admin_only: True` and field-level `admin_only` flags on Stripe/Discord/form fields
- Add `can_edit_page(page_key, section=None)` method to `accounts/models.py` `UserProfile`; define `ADMIN_ONLY_SECTIONS` dict
- Add `/site-config/` URL → `site_config_editor` view (admin-only form)
- Add `/api/site-config/` → `site_config_api` view (JSON patch endpoint with admin check)
- Template: `site_config_editor.html`

**Verification**: Admin updates Discord URL in CMS → publish → community page shows new URL on live site.

---

### Phase 3 — Simple text pages

**Goal**: Pages with only flat text fields (no arrays).

**Pages**: `community`, `join`, `research`, `about-us`

For `about-us`, the steering group sort order is a simple string array — straightforward in JSON.
For `join`, the benefits list is a simple string array.

**Astro changes** (for each page):
- Write the JSON data file with all editable text fields
- Modify the .astro page to import from JSON and replace hard-coded strings
- Keep all `getCollection()` calls and dynamic rendering unchanged

**CMS changes:**
- Add these 4 pages to `PAGE_TYPES`
- Extend `page_manager` view to list them
- Add `/pages/<key>/` → `page_editor` view (sections overview)
- Add `/pages/<key>/section/<section_key>/` → `page_section_editor` view (structured form for flat fields)
- Add `/api/pages/<key>/section/<section_key>/` → `page_section_api` view
- Templates: `page_editor.html`, `page_section_editor.html`

**Verification**: Editor updates Community page hero heading in CMS form → publishes → live site shows new heading.

---

### Phase 4 — Array sections (home, education, donate)

**Goal**: Handle structured arrays — accordion items, slider slides, testimonials, donation tiers.

**Pages**: `home`, `education`, `donate`

These are the most technically interesting pages. Arrays require:
- A repeating item sub-form in the section editor (add / edit / reorder / delete items)
- Strict full-array replacement on write (no partial-update ambiguity)

**Astro changes:**
- Write JSON data files for these 3 pages
- Modify .astro pages to `.map()` over arrays for all repeated sections
- For `education.astro`: core insight and objection accordions become `.map()` loops
- For `home/index.astro`: slider, testimonials, research/education/community cards become `.map()` loops
- For `donate.astro`: donation tiers become `.map()` loop; milestone settings from site-config

**CMS changes:**
- Add array section handling to `page_section_editor.html` (renders items in a sortable list; inline form per item for add/edit)
- Extend `page_section_api` to validate and write array-type sections
- Add these 3 pages to `PAGE_TYPES` with `type: "array"` on relevant section fields

**Verification**: Editor adds a new testimonial to the home page through the form editor → publishes → testimonial appears on the live home page.

---

### Phase 5 — Job Guarantee page

**Goal**: Handle the most complex single page (contributors array + long markdown body + Vimeo ID).

**Astro changes:**
- Write `job-guarantee.json`: `{title, publication_date, vimeo_video_id, contributors: [{name, photo_slug}], body}`
- Modify `job-guarantee.astro` to import from JSON; render body with `set:html`; map contributors

**CMS changes:**
- Add `job-guarantee` to `PAGE_TYPES` with a `markdown` field type for the body
- Add markdown textarea with preview to the section editor for `markdown`-typed fields

**Verification**: Editor updates publication date and body text through CMS → publishes → job-guarantee page reflects changes.

---

### Phase 6 — Chat integration

**Goal**: Let the AI chat interface also handle page edits.

**CMS changes:**
- Extend system prompt in `anthropic_service.py` with page editing instructions:
  - `read_page` action to load current JSON
  - `edit_page` action to patch a section
  - Critical rule: when editing an array section, always include the full array in `data`
- Handle `read_page` and `edit_page` action types in `send_message` view (alongside existing `read`, `create`, `edit`, `delete`)
- Add "Edit Page Content" as a suggested chat action for admin/editor users
- System prompt includes this rule: **"For accordion arrays, always read_page first, show the user the current list, then emit the full replacement array — never omit existing items."**

**Verification**: User says "Change the third testimonial on the home page to [quote]" in chat → Claude emits `edit_page` with correct full testimonials array → page updates correctly.

---

### Phase 7 — New page creation

**Goal**: Admin can create a new page from a template without touching source code.

**Templates available:**
| Template | Output | Use case |
|----------|--------|----------|
| `policy-page` | Simple title + markdown body | Privacy, terms, cookies, policy statements |
| `info-page` | Hero + markdown body | General informational pages |
| `accordion-page` | Hero + FAQ accordion sections | FAQ, curriculum pages |
| `feature-page` | Hero + feature cards + CTA | Campaign or topic landing pages |

**Creation workflow:**
1. Admin → `/pages/new/` → chooses template, enters slug + title
2. CMS generates: `src/data/pages/{slug}.json` (template defaults), `src/pages/{slug}.astro` (template file importing the JSON)
3. CMS updates `src/data/pages/manifest.json` to include the new page
4. Commits all three files in a single git commit
5. Railway deploys and the page is live

**CMS changes:**
- `/pages/new/` → `new_page_wizard` view (admin-only)
- Template `.astro` files stored in `mmtuk-cms/chat/page_templates/` (copied and modified for each new page)
- `create_new_page(slug, title, template_key)` function in `page_service.py`
- Template: `new_page_wizard.html`

**Verification**: Admin creates new "Our Impact" page using `feature-page` template → publish → `mmtuk.org/our-impact` is live.

---

### Phase 8 — Image management for pages

**Goal**: Organised image directories per page; image picker in section editor.

**Astro changes:**
- Create `public/images/pages/{page-slug}/` directory structure

**CMS changes:**
- Extend `image_catalog.py` with page-specific sections (home slider, education hero, donate cards, etc.)
- Add image picker modal to `page_section_editor.html` for `image_path`-typed fields
- The existing `/api/images/` endpoint and upload API support this via the `directory` parameter

**Verification**: Editor uploads new home page slider image → assigns it to slide 2 via image picker → publish → slider shows new image.

---

## Critical Files

### CMS — New files
- `c:\Dev\Claude\mmtuk-cms\chat\services\page_service.py` — core read/write/patch for page JSON
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\page_manager.html`
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\page_editor.html`
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\page_section_editor.html`
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\site_config_editor.html`
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\new_page_wizard.html` *(Phase 7)*
- `c:\Dev\Claude\mmtuk-cms\chat\page_templates\policy-page.astro` *(Phase 7)*
- `c:\Dev\Claude\mmtuk-cms\chat\page_templates\feature-page.astro` *(Phase 7)*

### CMS — Modified files
- `c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py` — add `PAGE_TYPES` dict and helper functions
- `c:\Dev\Claude\mmtuk-cms\accounts\models.py` — add `can_edit_page()` method, `ADMIN_ONLY_SECTIONS`
- `c:\Dev\Claude\mmtuk-cms\chat\urls.py` — add all new URL patterns
- `c:\Dev\Claude\mmtuk-cms\chat\views.py` — add page_manager, page_editor, page_section_editor, page_section_api, site_config_editor, site_config_api, new_page_wizard view functions
- `c:\Dev\Claude\mmtuk-cms\chat\templates\chat\base.html` — add "Pages" nav item
- `c:\Dev\Claude\mmtuk-cms\chat\services\anthropic_service.py` — extend system prompt with page editing rules *(Phase 6)*
- `c:\Dev\Claude\mmtuk-cms\chat\services\image_catalog.py` — add page-specific image sections *(Phase 8)*

### Astro site — New files
- `c:\Dev\Claude\MMTUK\src\data\pages\manifest.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\home.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\about-us.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\education.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\research.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\community.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\donate.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\join.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\job-guarantee.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\privacy-policy.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\terms-of-engagement.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\cookie-preferences.json`
- `c:\Dev\Claude\MMTUK\src\data\pages\site-config.json`

### Astro site — Modified files
- `c:\Dev\Claude\MMTUK\src\pages\index.astro` — import home.json + site-config.json
- `c:\Dev\Claude\MMTUK\src\pages\about-us.astro` — import about-us.json
- `c:\Dev\Claude\MMTUK\src\pages\education.astro` — import education.json
- `c:\Dev\Claude\MMTUK\src\pages\research.astro` — import research.json
- `c:\Dev\Claude\MMTUK\src\pages\community.astro` — import community.json + site-config.json
- `c:\Dev\Claude\MMTUK\src\pages\donate.astro` — import donate.json + site-config.json
- `c:\Dev\Claude\MMTUK\src\pages\join.astro` — import join.json + site-config.json
- `c:\Dev\Claude\MMTUK\src\pages\job-guarantee.astro` — import job-guarantee.json
- `c:\Dev\Claude\MMTUK\src\pages\privacy-policy.astro` — import privacy-policy.json
- `c:\Dev\Claude\MMTUK\src\pages\terms-of-engagement.astro` — import terms-of-engagement.json
- `c:\Dev\Claude\MMTUK\src\pages\cookie-preferences.astro` — import cookie-preferences.json
- `c:\Dev\Claude\MMTUK\src\layouts\BaseLayout.astro` — import site-config.json for announcement bar
- `c:\Dev\Claude\MMTUK\package.json` — add `marked` dependency (for markdown rendering in Astro)

---

## Key Technical Notes

**Markdown rendering in Astro**: Use `marked` (or `markdown-it`) to convert `body` strings to HTML. Pattern: `<div set:html={marked(data.body)} />`. An alternative is Astro's `<Content />` component but that requires a content collection — not appropriate here.

**Array deep-merge rule**: When writing an array section, `_deep_merge` always performs a full array replacement (not element-wise merge). This prevents stale items persisting after edits. The patch `{core_insights: {items: [...]}}` replaces the entire `items` array.

**JSON vs YAML**: JSON chosen over YAML because: (1) Python's `json` module is in stdlib, (2) Vite imports JSON natively, (3) no ambiguity around string quoting. The CMS's existing markdown+YAML approach remains for content collections.

**No schema changes to Astro content collections**: The `src/content/config.ts` file is untouched. Dynamic sections (getCollection calls in about-us, community, research, etc.) continue to work exactly as before.

**Backward compatibility**: During each phase, the Astro page is modified to import from JSON while the JSON file is being created in the same commit. There is no intermediate state where the import exists but the file doesn't.

**The `marked` dependency**: Only needed in the Astro build for pages that render markdown body strings (privacy-policy, terms, cookie-preferences, job-guarantee policy body). The existing briefings/articles use markdown content collections with Astro's built-in rendering — `marked` is purely for the page JSON body fields.

---

## Verification Plan (end-to-end)

After Phase 4 (array sections complete — full MVP):

1. **Build test**: `npm run build` in MMTUK repo completes without errors
2. **Render test**: Each migrated page renders identically to current production (screenshot comparison or manual review)
3. **Edit test**: Log in as Editor → navigate to Pages → edit Home hero heading → publish → confirm change on mmtuk.org/
4. **RBAC test**: Log in as Editor → attempt to edit site-config Stripe links → confirm "Admin only" fields are hidden / rejected
5. **RBAC test**: Log in as Group Lead → confirm Pages nav item is not visible
6. **Array test**: Log in as Editor → add a new testimonial to Home page → publish → confirm it appears on the live site
7. **Site-config test**: Log in as Admin → update Discord URL in site-config → publish → confirm new URL on community page
8. **Regression test**: Verify briefings, articles, news, bios (existing CMS-managed content) all still work correctly
