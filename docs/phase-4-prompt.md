# Phase 4 — Home Page, Donate Page & `object_array` Type: Session Prompt

## What this is

Phase 4 of the MMTUK CMS full website management plan. This prompt gives you everything you need to implement it in a single session.

---

## Prior work (Phases 1–3 — already shipped)

### Phase 1 — Foundation
- `src/data/pages/` directory, `manifest.json`, `page_service.py`, `PAGE_TYPES` dict
- Page Manager (`/pages/`), Page Editor (`/pages/<key>/`), Page Section Editor (`/pages/<key>/section/<key>/`)

### Phase 2 — Site Config
- `site-config.json` with `discord_url`, `stripe_links`, `action_network_form_id`, `founder_scheme`, `announcement_bar`
- Dedicated `/site-config/` editor and `/api/site-config/` API

### Phase 3 — Simple Text Pages
- Extracted text from community, join, research, about-us into JSON data files
- New `string_array` field type (textarea, one item per line) for `join_section.benefits` and `steering_group.order`
- CMS schema, view, and template updated to handle `string_array`

---

## What Phase 4 needs to do

**Goal:** Extract hardcoded text from the home page and donate page into JSON data files, and introduce a new `object_array` field type for sections that contain a variable-length list of structured items.

**Pages:** `index.astro` (home), `donate.astro`

**New field type:** `object_array` — an ordered list of objects, each with defined sub-fields. Used for the hero slider slides and home page testimonials.

---

## New field type: `object_array`

### Schema definition

```python
"slides": {
    "type": "object_array",
    "label": "Hero Slides",
    "item_fields": {
        "tag":         {"type": "string", "label": "Tag (e.g. Policy research)"},
        "text":        {"type": "string", "label": "Slide text / blurb"},
        "link_href":   {"type": "string", "label": "Link URL"},
        "link_label":  {"type": "string", "label": "Link label (visible text)"},
    }
},
```

### Editor rendering (`page_section_editor.html`)

Render as a repeating group of inputs, one group per item. Each group shows all `item_fields` as text inputs. Include **Add item** and **Remove** controls. No drag-to-reorder needed for Phase 4.

```html
{% elif field.type == 'object_array' %}
<div class="object-array-field" data-field-name="{{ field.name }}">
  <div class="object-array-items">
    {% for item in field.value %}
    <div class="object-array-item" data-index="{{ forloop.counter0 }}">
      <div class="object-array-item-header">
        <span class="object-array-item-label">Item {{ forloop.counter }}</span>
        <button type="button" class="btn btn-ghost btn-small remove-array-item">Remove</button>
      </div>
      {% for subfield_name, subfield_meta in field.item_fields.items %}
      <div class="form-group" style="margin-bottom: 0.75rem;">
        <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.3rem;">
          {{ subfield_meta.label }}
        </label>
        <input type="text"
               class="form-input object-array-subfield"
               data-subfield="{{ subfield_name }}"
               value="{{ item|get_item:subfield_name }}"
               style="width: 100%; box-sizing: border-box;">
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </div>
  <button type="button" class="btn btn-secondary btn-small add-array-item"
          data-field="{{ field.name }}"
          data-item-fields='{{ field.item_fields_json }}'>
    + Add item
  </button>
</div>
```

### JavaScript in `page_section_editor.html`

Before the form submits, the JS must collect `object_array` fields from the DOM and build proper arrays in the payload. Replace the simple `form.querySelectorAll('textarea, input')` loop to also handle `object_array`:

```javascript
// In the form submit handler, before fetch:
document.querySelectorAll('.object-array-field').forEach(function(container) {
    var fieldName = container.dataset.fieldName;
    var items = [];
    container.querySelectorAll('.object-array-item').forEach(function(itemEl) {
        var obj = {};
        itemEl.querySelectorAll('.object-array-subfield').forEach(function(input) {
            obj[input.dataset.subfield] = input.value;
        });
        items.push(obj);
    });
    payload[fieldName] = items;
});
```

Add/Remove item JS:
- **Add**: clone the item-fields template (from `data-item-fields` JSON), append a new empty group, update index labels
- **Remove**: remove the item's DOM group, update index labels

### View handling (`views.py`)

**In `page_section_editor`** — build `section_fields` for `object_array`:
```python
if field_meta.get('type') == 'object_array':
    value = section_data.get(field_name, [])  # already a list of dicts
    # Pass item_fields and item_fields_json for template use
    section_fields.append({
        ...
        'value': value,
        'item_fields': field_meta.get('item_fields', {}),
        'item_fields_json': json.dumps(field_meta.get('item_fields', {})),
    })
```

**In `page_section_api`** — no conversion needed: the payload already arrives as a list of objects (the JS builds it correctly before posting).

### Django template filter

To render `{{ item|get_item:subfield_name }}` you need a custom template filter:

```python
# In a templatetags file (e.g., chat/templatetags/chat_extras.py)
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, '')
```

Register it and load it in the template: `{% load chat_extras %}`.

---

## Detailed work per page

### 1. `index.astro` → `home.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/index.astro`

**DO NOT extract:**
- Slider images (Phase 8)
- Feature card images (Phase 8)
- The contact email `contact@mmtuk.org` (leave hardcoded for now)

**JSON structure:**

```json
{
  "meta": {
    "title": "Home",
    "description": "MMTUK is an independent research organisation producing evidence-based economic analysis informed by Modern Monetary Theory. Explore our articles, education resources and community."
  },
  "hero": {
    "heading": "Driving Economic Change",
    "tagline": "MMTUK is an independent research organisation dedicated to producing high-quality, evidence-based analysis informed by Modern Monetary Theory (MMT).",
    "slides": [
      {
        "tag": "Policy research",
        "text": "A Counter-Inflationary Job Guarantee for the UK — now published",
        "link_href": "/job-guarantee",
        "link_label": "A Counter-Inflationary Job Guarantee for the UK"
      },
      {
        "tag": "Education & training",
        "text": "Courses and workshops equipping citizens and leaders with modern money literacy skills.",
        "link_href": "",
        "link_label": ""
      },
      {
        "tag": "Community outreach",
        "text": "Events, collaborations, and campaigns connecting research with real community priorities across Britain.",
        "link_href": "",
        "link_label": ""
      }
    ]
  },
  "research_section": {
    "heading": "Academic Research",
    "description": "Strategic research and targeted advocacy to transform Britain's economic landscape through innovative policy frameworks",
    "card_1_heading": "The Job Guarantee",
    "card_1_body": "Our UK-focused proposal is in advanced draft form. It demonstrates how MMT can achieve full employment and price stability.",
    "card_1_href": "/job-guarantee",
    "card_1_button_label": "Read more",
    "card_2_heading": "Zero Interest Rate Policy (ZIRP)",
    "card_2_body": "A UK framework for a standing 0% policy rate, with fiscal stabilisers managing demand and prices.",
    "card_2_href": "/research",
    "card_2_button_label": "Read more"
  },
  "education_section": {
    "heading": "Education & Training",
    "description": "Explore our library and briefings for clear, practical guides to UK macro-economic policy.",
    "card_1_heading": "The MMTUK library",
    "card_1_body": "Searchable library of papers, podcasts, articles and more on economics through the lens of MMT.",
    "card_1_href": "",
    "card_1_button_label": "Coming soon",
    "card_2_heading": "Our Briefings",
    "card_2_body": "Concise briefings from MMTUK and our guests explaining UK macro policy with practical, actionable insights.",
    "card_2_href": "/research/briefings",
    "card_2_button_label": "Read more"
  },
  "community_section": {
    "heading": "Community & Network",
    "description": "Connect with other people interested in MMT by joining local groups, public events and active online discussions.",
    "card_1_heading": "Local Groups",
    "card_1_body": "Join or start local MMT groups, supported and connected nationwide.",
    "card_1_href": "/community#Network",
    "card_1_button_label": "Read more",
    "card_2_heading": "Events",
    "card_2_body": "Join talks, workshops, and conferences we host and attend nationwide.",
    "card_2_href": "/community#Events",
    "card_2_button_label": "Read more",
    "card_3_heading": "Online",
    "card_3_body": "Debate, learn, and organise together in our moderated online community.",
    "card_3_href": "/community#discord",
    "card_3_button_label": "Read more"
  },
  "testimonials": {
    "items": [
      {
        "quote": "MMTUK turns complex monetary operations into plain English, empowering people to see policy choices clearly and demand better, more humane economics.",
        "name": "Patricia Pino",
        "title": "Executive Director & Academic Researcher, MMTUK"
      },
      {
        "quote": "A rare mix of heterodox depth and public pedagogy. MMTUK elevates debate and equips citizens to challenge harmful myths.",
        "name": "Dr Phil Armstrong",
        "title": "Founder, MMTUK"
      },
      {
        "quote": "MMTUK marries rigorous scholarship with practical organising. It's a hub where democratic priorities and monetary reality finally meet.",
        "name": "Dr David Merrill",
        "title": "Founder, MMTUK"
      }
    ]
  },
  "contact": {
    "heading": "Contact Us",
    "tagline": "Be part of the economic transformation that challenges conventional thinking and drives meaningful policy change"
  }
}
```

**CMS sections:** `meta`, `hero`, `research_section`, `education_section`, `community_section`, `testimonials`, `contact`

- `hero.slides` → `object_array` with item_fields: `tag`, `text`, `link_href`, `link_label`
- `testimonials.items` → `object_array` with item_fields: `quote`, `name`, `title`
- All other fields → `string` (numbered flat fields, same Phase 3 pattern)

**Astro template notes:**
- Hero slider: the 3 slides are currently hard-coded `<div class="header102_slide w-slide">` blocks. After Phase 4, render them from `pageData.hero.slides.map(slide => ...)`. The first slide has a special structure (linked image, linked title) vs. slides 2–3 (unlinked image, no link). Consider: either make all slides use a uniform structure (link optional), or keep slides 2–3 as separate named fields if they're structurally different. **Recommendation:** Keep the slider as `object_array` but note that slide rendering in the template must handle `link_href` being empty (omit the `<a>` wrapper if blank).
- Testimonials: straightforward — `pageData.testimonials.items.map(t => ...)` replaces the 3 hardcoded testimonial cards.

---

### 2. `donate.astro` → `donate.json`

**Astro file:** `c:/Dev/Claude/MMTUK/src/pages/donate.astro`

**DO NOT extract:**
- `siteConfig.stripe_links.*` — already from site-config.json (Phase 2)
- `siteConfig.founder_scheme.*` — already from site-config.json (Phase 2)
- `MilestoneProgress` component props — driven by site-config

**JSON structure:**

```json
{
  "meta": {
    "title": "Donate",
    "description": "Support MMTUK's mission to promote understanding of Modern Monetary Theory. Your donation funds independent research, education programmes and community outreach across the UK."
  },
  "hero": {
    "heading": "Support modern economics",
    "tagline": "Join our mission to advance progressive economic thinking through research, collaboration, and innovative funding strategies."
  },
  "founder_section": {
    "heading": "founder member scheme",
    "tagline": "Calling 100 visionary donors to make a difference",
    "body": "Be among the first 100 donors to contribute £100 or more within 100 days and be recognised as a founding supporter of MMTUK."
  },
  "founder_cta": {
    "heading": "fuel our foundations",
    "plan_label": "Founder Member donation",
    "plan_amount": "£100",
    "button_label": "Join as a Founder Member of MMTUK"
  },
  "research_donations": {
    "heading": "research Donations",
    "body": "Support our research projects. Every contribution drives meaningful change.",
    "bullet_1": "Fund groundbreaking research initiatives",
    "bullet_2": "Support emerging economic scholars",
    "bullet_3": "Advance progressive economic thinking"
  },
  "pricing": {
    "heading": "Research Donation levels",
    "tagline": "Choose a contribution that matches your commitment to economic research",
    "supporter_label": "Supporter",
    "supporter_amount": "£5",
    "supporter_period": "Monthly contribution",
    "supporter_button": "Donate now",
    "founder_label": "Founder",
    "founder_amount": "£100",
    "founder_period": "One-off donation",
    "founder_button": "Donate now",
    "patron_label": "Patron",
    "patron_amount": "£?",
    "patron_period": "One-off donation",
    "patron_button": "Donate now"
  },
  "thank_you": {
    "heading": "thank you for Transforming economics with us",
    "body": "Your contribution matters. Help us reshape economic understanding through collaborative, progressive research."
  }
}
```

**CMS sections:** `meta`, `hero`, `founder_section`, `founder_cta`, `research_donations`, `pricing`, `thank_you` — all flat `string` fields.

---

## CMS changes needed

### 1. `content_schema/schemas.py` — Add 2 pages to PAGE_TYPES

Add `home` and `donate`. Home page `hero` section has `slides` as `object_array`. Home page `testimonials` section has `items` as `object_array`.

### 2. `chat/views.py` — Handle `object_array` type

In `page_section_editor`:
- Detect `object_array` type
- Pass `value` (list of dicts, already correct from JSON), `item_fields`, and `item_fields_json` (for the Add-item JS template)

In `page_section_api`:
- No coercion needed — the JS builds proper arrays before posting, so the body arrives with the correct structure

### 3. `chat/templates/chat/page_section_editor.html` — Render object_array

Add `{% elif field.type == 'object_array' %}` branch with:
- Repeating item groups (one per list item)
- Sub-field text inputs inside each group with `data-subfield` attribute
- Remove button per item
- Add item button at the bottom
- JS to handle Add/Remove and to collect items into payload on submit

### 4. Django template filter — `get_item`

Create `chat/templatetags/chat_extras.py` with a `get_item` filter to allow `{{ item|get_item:key }}` in the template. Register in the `chat` app's `templatetags` package.

### 5. `manifest.json` — Add 2 entries

```json
{ "key": "home",   "title": "Home",   "route": "/" },
{ "key": "donate", "title": "Donate", "route": "/donate" }
```

### 6. Astro pages — Import from JSON

For each page:
- Add `import pageData from '../data/pages/{page}.json';`
- Replace hardcoded text with `{pageData.section.field}`
- For `object_array` fields, use `.map()` in the template

---

## Key patterns from prior phases (carry forward)

1. JSON files live in `src/data/pages/` in the Astro repo
2. Astro import: `import pageData from '../data/pages/home.json';`
3. CMS reads/writes via `page_service.py` — the `_deep_merge` function replaces arrays entirely (no append), which is correct for `object_array`
4. Section editor at `/pages/<key>/section/<section_key>/`
5. RBAC: `PAGE_EDITOR_ROLES = {"admin", "editor"}`, no `admin_only` needed for these pages
6. Git workflow: write JSON → commit → push → Railway auto-deploys Astro site
7. `is:inline` scripts cannot use Astro expressions — use `data-*` attributes

## Important constraints

- **Only live pages** — `founders.astro` excluded (no live links)
- **Don't touch `siteConfig.*`** values — they're in site-config.json already
- **Image paths** stay hardcoded in `.astro` templates — Phase 8
- **Build verification**: `cd c:/Dev/Claude/MMTUK && npm run build` must pass with zero errors
- The home page slider has a structural difference between slide 1 (has a linked image + linked title) and slides 2–3 (unlinked image, text only). When converting to `object_array`, make the template handle `link_href` being empty — if empty, render as plain text/div rather than an `<a>` tag.

## Repos

- **Astro site**: `c:/Dev/Claude/MMTUK` (branch: main)
- **CMS**: `c:/Dev/Claude/mmtuk-cms` (branch: master)

## Ship

When done, commit and push both repos. The CMS deploys via Railway from master. The Astro site deploys via Railway from main.
