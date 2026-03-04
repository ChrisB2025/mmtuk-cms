# Phase 3 — Simple Text Pages: Session Prompt

## What this is

Phase 3 of the MMTUK CMS full website management plan. This prompt gives you everything you need to implement it in a single session.

## Prior work (Phases 1 & 2 — already shipped)

### Phase 1 — Foundation (commit `c75b853` in MMTUK, `11142c4` in mmtuk-cms)
- Created `src/data/pages/` directory in the Astro repo with JSON data files for privacy-policy, terms-of-engagement, cookie-preferences
- Created `manifest.json` as the page registry
- Built `chat/services/page_service.py` (read_page_data, write_page_data, apply_page_patch, _deep_merge)
- Added `PAGE_TYPES` dict to `content_schema/schemas.py`
- Added Page Manager (`/pages/`), Page Editor (`/pages/<key>/`), Page Section Editor (`/pages/<key>/section/<key>/`), and Page Section API (`/api/pages/<key>/section/<key>/`)
- Added "Pages" to sidebar nav and command palette

### Phase 2 — Site Config
- Created `site-config.json` with discord_url, stripe_links, action_network_form_id, founder_scheme settings, announcement_bar
- Updated community.astro (Discord URL), donate.astro (Stripe links, countdown, milestone), join.astro (Action Network form ID), BaseLayout.astro (announcement bar)
- Added site-config to PAGE_TYPES with admin_only flags, dedicated `/site-config/` editor and `/api/site-config/` API
- Added sidebar + command palette links for admin users
- **founders.astro was excluded** — it's a Webflow leftover with no live links to it

## What Phase 3 needs to do

**Goal:** Extract hard-coded text from 4 Astro pages into JSON data files, and register them in the CMS so editors can update them via the existing form-based section editor.

**Pages:** community, join, research, about-us

These pages contain only flat text fields and simple string arrays — no complex nested arrays of objects (that's Phase 4). The existing page editor infrastructure from Phase 1 handles these pages with no new CMS UI code needed.

---

## Detailed work per page

### 1. `community.astro` → `community.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/community.astro`

**DO NOT extract** (already dynamic):
- `getCollection('localGroups')` — drives Local Groups grid
- `getCollection('localEvents')` — drives Upcoming Events grid
- `siteConfig.discord_url` — already from site-config.json (Phase 2)

**JSON structure:**
```json
{
  "meta": {
    "title": "Community",
    "description": "Connect with the MMTUK community. Find local groups..."
  },
  "hero": {
    "heading": "Community",
    "tagline": "Meet, learn and organise with people building a better UK economy."
  },
  "local_groups": {
    "heading": "Local Groups",
    "description": "Connect with MMT supporters in your area to share knowledge, discuss regional issues...",
    "button_label": "Get involved"
  },
  "events": {
    "heading": "Upcoming events",
    "description": "Discover critical conversations shaping economic understanding",
    "button_label": "Learn more"
  },
  "discord": {
    "heading": "MMTUK Discord Server",
    "description": "Join our moderated UK community on Discord for lively discussion, learning, events...",
    "button_label": "Join Discord here"
  }
}
```

**CMS sections:** `meta`, `hero`, `local_groups`, `events`, `discord` — all flat string fields.

---

### 2. `join.astro` → `join.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/join.astro`

**DO NOT extract:**
- `siteConfig.action_network_form_id` — already from site-config.json (Phase 2)

**JSON structure:**
```json
{
  "meta": {
    "title": "Join",
    "description": "Join MMTUK and help advance public understanding..."
  },
  "hero": {
    "heading": "Join the movement for meaningful change",
    "tagline": "Connect with local groups driving community impact. Make a difference where you live."
  },
  "join_section": {
    "heading": "Join the MMTUK Community",
    "subtitle": "Register your interest in our research and policy initiatives",
    "intro": "We are building a register of activists across the country...",
    "benefits": [
      "Create a network of UK based MMT activists to support...",
      "Support each others learning of MMT fundamentals.",
      "Coordinate larger campaigns, dissemination and educational activities.",
      "Create high quality MMT informed policy documents to take...",
      "Have a collection of experts at the ready to make the case...",
      "We are very keen on getting connected with people interested..."
    ]
  }
}
```

**CMS sections:** `meta`, `hero`, `join_section`. The `benefits` field is a simple string array — render in the section editor as a multi-line textarea (one item per line) or as individual text inputs. The simplest approach: use a `string_array` type that the section editor renders as a textarea with one item per line (split on `\n` when saving).

---

### 3. `research.astro` → `research.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/research.astro`

**DO NOT extract:**
- `getCollection('briefings')` — drives the MMT Briefings card section (content is dynamic)

**JSON structure:**
```json
{
  "meta": {
    "title": "Research",
    "description": "Explore MMTUK research and publications."
  },
  "hero": {
    "heading": "Research",
    "tagline": "Strategic research and targeted advocacy to transform Britain's economic landscape through innovative policy frameworks"
  },
  "policy_areas": {
    "heading": "Our Priority Policy areas",
    "description": "Strategic research and targeted advocacy to transform Britain's economic landscape..."
  },
  "job_guarantee": {
    "heading": "The Job Guarantee",
    "description": "Our inaugural policy paper, published 25 February 2026, demonstrates how MMT can achieve...",
    "feature_1": "Guarantee a paid public option at £15 per hour, centrally funded and locally delivered...",
    "feature_2": "Operate as a counter-inflation automatic stabiliser by converting unemployment...",
    "feature_3": "Deliver strong net fiscal and social returns through lower benefit spend...",
    "button_label": "Read more here",
    "button_href": "/job-guarantee"
  },
  "zirp": {
    "heading": "Zero Interest Rate Policy (ZIRP)",
    "description": "A permanent 0% Central Bank Interest rate, with fiscal policy doing the steering",
    "feature_1": "Set Bank Rate at 0 percent, replace routine gilt issuance with reserves...",
    "feature_2": "Manage demand through automatic stabilisers and targeted fiscal measures...",
    "feature_3": "Offer safe saving via NS&I and regulated products, publish a gilt market transition plan...",
    "wip_notice": "We are currently working on a draft for this policy"
  },
  "briefings": {
    "heading": "MMT Briefings",
    "description": "Our affiliated authors critique public economic commentary and rebut anti-MMT polemic...",
    "tag_label": "Briefing",
    "read_button_label": "Read briefing",
    "view_all_label": "View All Briefings"
  },
  "approach": {
    "heading": "Our Approach to policy Research",
    "description": "Navigating complex economic and social landscapes through research and understanding...",
    "card_1_heading": "How we approach research",
    "card_1_body": "We blend academic rigor with practical application...",
    "card_2_heading": "What makes our work unique",
    "card_2_body": "We bridge academic theory and real-world impact...",
    "card_3_heading": "Our research methodology",
    "card_3_body": "We employ interdisciplinary approaches that challenge conventional thinking...",
    "card_4_heading": "Impact of our work",
    "card_4_body": "Our research influences policy, challenges economic paradigms...",
    "card_5_heading": "Collaboration and transparency",
    "card_5_body": "We believe in open research and collaborative knowledge creation..."
  }
}
```

**CMS sections:** `meta`, `hero`, `policy_areas`, `job_guarantee`, `zirp`, `briefings`, `approach` — all flat string fields. The approach cards use numbered fields (card_1_heading, card_1_body, etc.) to keep them flat rather than introducing arrays (Phase 4 pattern).

---

### 4. `about-us.astro` → `about-us.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/about-us.astro`

**DO NOT extract:**
- `getCollection('bios')` — drives Steering Group and Advisory Board member cards
- `getCollection('localEvents')` — drives MMTUK Events section
- `getCollection('news')` — drives MMTUK News accordion

**JSON structure:**
```json
{
  "meta": {
    "title": "About Us",
    "description": "Learn about MMTUK and our team."
  },
  "hero": {
    "heading": "We Are Academics, Activists & Organisers",
    "description": "We bring together leading minds from the UK MMT community to deliver rigorous research..."
  },
  "news": {
    "heading": "MMTUK News",
    "description": "Latest announcements from MMTUK",
    "button_label": "Read more"
  },
  "events": {
    "heading": "MMTUK Events",
    "description": "Upcoming talks, meetups, and gatherings across the UK",
    "button_label": "Learn more"
  },
  "steering_group": {
    "heading": "Steering Group",
    "description": "Dedicated minds driving economic and social research forward",
    "order": [
      "Dr Phil Armstrong",
      "Dr Stephanie Linkogle",
      "Patricia Pino",
      "David Merrill",
      "Andrew Berkeley",
      "Richard Tye",
      "Steve Laughton",
      "Vincent Gomez",
      "David McNab"
    ]
  },
  "advisory_board": {
    "heading": "ADVISORY BOARD",
    "description": "Independent guidance from leading global MMT economists."
  }
}
```

**CMS sections:** `meta`, `hero`, `news`, `events`, `steering_group`, `advisory_board`. The `order` field in `steering_group` is a `string_array` — same pattern as `benefits` in join.json.

---

## CMS changes needed

### 1. `content_schema/schemas.py` — Add 4 pages to PAGE_TYPES

Add `community`, `join`, `research`, `about-us` to the existing `PAGE_TYPES` dict. Each page needs its sections and fields defined as shown above. All fields are `type: "string"` except:
- `join_section.benefits` → `type: "string_array"` (new type)
- `steering_group.order` → `type: "string_array"` (new type)

### 2. `chat/views.py` — Handle `string_array` type

The existing `page_section_editor` view and `page_section_api` view need to handle the new `string_array` type:
- **Editor**: Render as a `<textarea>` with one item per line
- **API**: On save, split the textarea value by newlines and strip whitespace to produce a JSON array. On load, join the array with newlines for display.

### 3. `chat/templates/chat/page_section_editor.html` — Render string_array

Add a template condition for `field.type == 'string_array'` — render as a textarea (similar to markdown but without the preview tab).

### 4. `manifest.json` — Add 4 new entries

Add community, join, research, about-us to the manifest.

### 5. Astro pages — Import from JSON

For each of the 4 pages:
- Add `import pageData from '../data/pages/{page}.json';` to frontmatter
- Replace each hard-coded string with `{pageData.section.field}`
- For string arrays (benefits, steering order), use `.map()` to render

---

## Key patterns established in prior phases

1. **JSON data files** live in `src/data/pages/` in the Astro repo
2. **Astro imports**: `import pageData from '../data/pages/community.json';`
3. **CMS reads/writes** via `page_service.py` (read_page_data, write_page_data, apply_page_patch)
4. **Section editor** at `/pages/<key>/section/<section_key>/` — already works for string and markdown fields
5. **Page editor** at `/pages/<key>/` — lists sections with Edit buttons
6. **Page manager** at `/pages/` — lists all pages with Edit buttons
7. **RBAC**: PAGE_EDITOR_ROLES = {"admin", "editor"}, ADMIN_ONLY_PAGES for restricted pages, ADMIN_ONLY_FIELDS for restricted fields
8. **Git workflow**: write JSON → commit → push → Railway auto-deploys Astro site
9. **`is:inline` scripts** can't use Astro template expressions — use data-attributes + getAttribute()
10. **Site-config values** (discord_url, stripe_links, etc.) are imported separately via `import siteConfig from '../data/pages/site-config.json'` — don't duplicate these in page JSON files

## Important constraints

- **Only live pages** — exclude founders.astro and any other Webflow leftover pages not linked from the live site
- **Don't touch getCollection() calls** — dynamic content sections (bios, events, news, briefings, localGroups) stay exactly as they are
- **Don't touch site-config imports** — values already in site-config.json from Phase 2 stay there
- **Build verification**: Run `cd c:/Dev/Claude/MMTUK && npm run build` after all Astro changes — must pass with zero errors
- **Image paths** (hero backgrounds, Discord image, etc.) stay hard-coded in the .astro template for now — image management is Phase 8. Only extract *text* content.

## Repos

- **Astro site**: `c:/Dev/Claude/MMTUK` (branch: main)
- **CMS**: `c:/Dev/Claude/mmtuk-cms` (branch: master)

## Ship

When done, commit and push both repos. The CMS deploys via Railway from master. The Astro site deploys via Railway from main.
