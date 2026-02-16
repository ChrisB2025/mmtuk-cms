# MMTUK CMS - Schema Audit Report
**Date:** 2026-02-16
**Phase:** Phase 2, Task #3

## Executive Summary

This audit compared three schema definitions:
1. **Astro Zod schemas** (`c:\Dev\Claude\MMTUK\src\content.config.ts`) - Canonical source of truth
2. **JSON Schema generator** (`c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs`) - Mirrors Astro schemas
3. **CMS Python schemas** (`c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py`) - Django validator

**Status:** ⚠️ **7 Critical Issues Found**

### Key Findings:
- ❌ **1 missing content type** (localGroups)
- ⚠️ **6 field optionality mismatches** (will cause validation failures)
- ℹ️ **1 default value mismatch** (article.author)
- ℹ️ **2 intentional type constraints** (localGroup enums - stricter in CMS)

---

## Collection Coverage

| Astro Collection | JSON Generator | CMS Schema | Status |
|-----------------|----------------|------------|--------|
| articles        | ✅ articles     | ✅ article  | ✅ Present |
| briefings       | ✅ briefings    | ✅ briefing | ✅ Present |
| news            | ✅ news         | ✅ news     | ✅ Present |
| bios            | ✅ bios         | ✅ bio      | ✅ Present |
| ecosystem       | ✅ ecosystem    | ✅ ecosystem| ✅ Present |
| localNews       | ✅ localNews    | ✅ local_news | ✅ Present |
| localEvents     | ✅ localEvents  | ✅ local_event | ✅ Present |
| localGroups     | ✅ localGroups  | ❌ **MISSING** | ❌ **CRITICAL** |

---

## Issue #1: Missing Content Type - localGroups

**Severity:** 🔴 **CRITICAL**

**Impact:** Users cannot create or manage local groups via CMS. This is a complete feature gap.

**Astro Schema** (`content.config.ts:88-100`):
```typescript
const localGroups = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/localGroups' }),
  schema: z.object({
    name: z.string(),
    slug: z.string(),
    title: z.string(),
    tagline: z.string(),
    headerImage: z.string().default(''),
    leaderName: nullableStr(),
    leaderIntro: nullableStr(),
    discordLink: nullableStr(),
    active: z.boolean().default(true),
  }),
});
```

**CMS Schema:** ❌ Not defined in `CONTENT_TYPES` dictionary

**Required Fields:**
- name (string, required)
- slug (string, required)
- title (string, required)
- tagline (string, required)
- headerImage (string, default: '')
- leaderName (string, optional)
- leaderIntro (string, optional)
- discordLink (string, optional)
- active (boolean, default: true)

**Action Required:** Add `local_group` definition to `schemas.py`

---

## Issue #2: Briefing Field Optionality Mismatches

**Severity:** 🟠 **HIGH** - Will cause validation failures for valid Astro content

### Field: `summary`
- **Astro:** `nullableStr()` → Optional (can be null/undefined)
- **CMS:** `{"type": "string"}` → Required
- **Impact:** Briefings without summaries will fail CMS validation but pass Astro build

### Field: `thumbnail`
- **Astro:** `nullableStr()` → Optional
- **CMS:** `{"type": "string", "description": "Card image path..."}` → Required
- **Impact:** Briefings without thumbnails will fail CMS validation

### Field: `sourceUrl`
- **Astro:** `nullableStr()` → Optional
- **CMS:** `{"type": "string", "description": "Original article URL..."}` → Required
- **Impact:** Manually created briefings (not imported from Substack) will fail validation

**Action Required:** Mark these fields as `"optional": True` in CMS schemas.py

---

## Issue #3: News Field Optionality Mismatch

**Severity:** 🟠 **HIGH**

### Field: `summary`
- **Astro:** `nullableStr()` → Optional
- **CMS:** `{"type": "string"}` → Required
- **Impact:** News items without summaries will fail CMS validation

**Action Required:** Mark `summary` as `"optional": True` in CMS schemas.py

---

## Issue #4: Ecosystem Field Optionality Mismatches

**Severity:** 🟠 **MEDIUM**

### Field: `types`
- **Astro:** `z.array(z.string()).optional()` → Optional array
- **CMS:** `{"type": "string_array", "description": "Taxonomy tags..."}` → Required
- **Impact:** Ecosystem entries without type tags will fail CMS validation

### Field: `summary`
- **Astro:** `nullableStr()` → Optional
- **CMS:** `{"type": "string"}` → Required
- **Impact:** Ecosystem entries without summaries will fail CMS validation

**Action Required:** Mark both fields as `"optional": True` in CMS schemas.py

---

## Issue #5: Article Author Default Value Mismatch

**Severity:** 🟡 **LOW** - Cosmetic issue, may cause confusion

### Field: `author`
- **Astro:** `z.string()` → Required, no default
- **CMS:** `{"type": "string", "default": "MMTUK"}` → Has default value
- **Impact:** CMS will auto-fill "MMTUK" but Astro expects explicit author. Minor UX inconsistency.

**Recommendation:** Remove default from CMS to match Astro (force explicit author selection)

**Alternative:** Keep CMS default for better UX, but ensure it's always written to frontmatter

---

## Issue #6: LocalGroup Enum Constraints (Intentional Difference)

**Severity:** ℹ️ **INFO** - Likely intentional for stricter CMS validation

### In `local_news` and `local_event`:

**Astro:**
```typescript
localGroup: z.string()  // Any string allowed
```

**CMS:**
```python
"localGroup": {
    "type": "enum",
    "options": ["brighton", "london", "oxford", "pennines", "scotland", "solent"],
    "description": "Must match an existing local group slug",
}
```

**Analysis:** The CMS is stricter (validates against known local groups) while Astro allows any string. This is a **good pattern** - the CMS prevents typos by enforcing enum, while Astro remains flexible.

**Recommendation:** Keep as-is. This is intentional and beneficial.

---

## Issue #7: Local Event Date Type Description

**Severity:** ℹ️ **INFO** - Documentation inconsistency

### Field: `date`
- **Astro:** `z.coerce.date()` - Coerces strings to Date objects, handles ISO datetime strings
- **CMS:** `{"type": "datetime", "description": "Event date and time in ISO format"}`

**Analysis:** Functionally equivalent. Astro's `coerce.date()` accepts datetime strings. CMS description says "datetime" for clarity.

**Recommendation:** No action needed. Descriptions are accurate.

---

## Schema Alignment Table

### Articles ✅
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| title | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| category | enum (required) | enum (required) | ✅ Match |
| layout | enum (default: 'default') | enum (default: 'default') | ✅ Match |
| sector | string (default: 'Economics') | string (default: 'Economics') | ✅ Match |
| author | string (required) | string ⚠️ (default: 'MMTUK') | ⚠️ Default mismatch |
| authorTitle | optional | optional | ✅ Match |
| pubDate | date (required) | date (required) | ✅ Match |
| readTime | number (default: 5) | number (default: 5) | ✅ Match |
| summary | optional | optional | ✅ Match |
| thumbnail | optional | optional | ✅ Match |
| mainImage | optional | optional | ✅ Match |
| featured | boolean (default: false) | boolean (default: false) | ✅ Match |
| color | optional | optional | ✅ Match |

### Briefings ⚠️
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| title | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| author | string (required) | string (required) | ✅ Match |
| authorTitle | optional | optional | ✅ Match |
| pubDate | date (required) | date (required) | ✅ Match |
| readTime | number (default: 5) | number (default: 5) | ✅ Match |
| summary | optional | ❌ required | ❌ **MISMATCH** |
| thumbnail | optional | ❌ required | ❌ **MISMATCH** |
| mainImage | optional | optional | ✅ Match |
| featured | boolean (default: false) | boolean (default: false) | ✅ Match |
| draft | boolean (default: false) | boolean (default: false) | ✅ Match |
| sourceUrl | optional | ❌ required | ❌ **MISMATCH** |
| sourceTitle | optional | optional | ✅ Match |
| sourceAuthor | optional | optional | ✅ Match |
| sourcePublication | optional | optional | ✅ Match |
| sourceDate | optional | optional | ✅ Match |

### News ⚠️
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| title | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| date | date (required) | date (required) | ✅ Match |
| category | enum (required) | enum (required) | ✅ Match |
| summary | optional | ❌ required | ❌ **MISMATCH** |
| thumbnail | optional | optional | ✅ Match |
| mainImage | optional | optional | ✅ Match |
| registrationLink | optional | optional | ✅ Match |

### Bios ✅
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| name | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| role | string (required) | string (required) | ✅ Match |
| photo | optional | optional | ✅ Match |
| linkedin | optional | optional | ✅ Match |
| twitter | optional | optional | ✅ Match |
| website | optional | optional | ✅ Match |
| advisoryBoard | boolean (default: false) | boolean (default: false) | ✅ Match |

### Ecosystem ⚠️
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| name | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| country | string (default: 'UK') | string (default: 'UK') | ✅ Match |
| types | optional array | ❌ required array | ❌ **MISMATCH** |
| summary | optional | ❌ required | ❌ **MISMATCH** |
| logo | optional | optional | ✅ Match |
| website | optional | optional | ✅ Match |
| twitter | optional | optional | ✅ Match |
| facebook | optional | optional | ✅ Match |
| youtube | optional | optional | ✅ Match |
| discord | optional | optional | ✅ Match |
| status | enum (default: 'Active') | enum (default: 'Active') | ✅ Match |

### LocalNews ✅
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| heading | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| text | string (required) | string (required) | ✅ Match |
| localGroup | string (required) | enum (required) ℹ️ | ℹ️ Intentionally stricter |
| date | date (required) | date (required) | ✅ Match |
| link | optional | optional | ✅ Match |
| image | optional | optional | ✅ Match |

### LocalEvents ✅
| Field | Astro | CMS | Status |
|-------|-------|-----|--------|
| title | string (required) | string (required) | ✅ Match |
| slug | string (required) | string (required) | ✅ Match |
| localGroup | string (required) | enum (required) ℹ️ | ℹ️ Intentionally stricter |
| date | date (required) | datetime (required) | ✅ Match (functionally) |
| tag | string (required) | string (required) | ✅ Match |
| location | string (required) | string (required) | ✅ Match |
| description | string (required) | string (required) | ✅ Match |
| link | optional | optional | ✅ Match |
| image | optional | optional | ✅ Match |
| partnerEvent | optional | optional | ✅ Match |

### LocalGroups ❌
**Status:** ❌ **NOT DEFINED IN CMS**

---

## Recommended Actions

### Priority 1: Critical (Blocking)
1. ✅ **Add localGroups content type** to `schemas.py` with all 9 fields

### Priority 2: High (Validation Failures)
2. ✅ **Fix briefing field optionality:**
   - Mark `summary` as optional
   - Mark `thumbnail` as optional
   - Mark `sourceUrl` as optional

3. ✅ **Fix news field optionality:**
   - Mark `summary` as optional

4. ✅ **Fix ecosystem field optionality:**
   - Mark `types` as optional
   - Mark `summary` as optional

### Priority 3: Low (Cosmetic)
5. ⚠️ **Review article.author default** - Consider removing "MMTUK" default to match Astro

### No Action Required
6. ℹ️ **Keep localGroup enum constraints** - Beneficial stricter validation in CMS
7. ℹ️ **Keep date/datetime description** - Functionally equivalent

---

## Validation Test Plan

After implementing fixes, test each content type with:

### Test Case 1: Minimal Valid Content
- Provide only required fields
- Verify passes both CMS and Astro validation

### Test Case 2: Omit Optional Fields
- Create content without `summary`, `thumbnail`, etc.
- Verify passes validation (currently fails for mismatched fields)

### Test Case 3: Invalid Enum Values
- Test with invalid `category`, `status`, `localGroup` values
- Verify fails validation with clear error messages

### Test Case 4: Type Mismatches
- Test with wrong types (string instead of number, etc.)
- Verify validation catches errors

### Test Case 5: LocalGroups CRUD
- Create, read, update, delete local group via CMS
- Verify generates valid Markdown files
- Verify passes Astro build

---

## Schema Evolution Pattern

**Pattern for future schema changes:**

1. **Update Astro schema first** (`content.config.ts`) - Source of truth
2. **Update JSON generator** (`generate-schemas.mjs`) - Keep in sync
3. **Update CMS schema** (`schemas.py`) - Match Astro optionality exactly
4. **Run schema audit** - Use this report as template
5. **Test validation** - Sample data for each content type
6. **Update documentation** - If field meanings change

**Pro tip:** Add this to CI/CD:
```bash
# In Astro repo
npm run build  # Validates all content against schemas
node scripts/generate-schemas.mjs  # Regenerate JSON schemas

# In CMS repo
python manage.py test content_schema  # Unit test schema validators
```

---

## Files Modified (To Be Done)

### 1. `c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py`
**Changes:**
- Add `local_group` content type definition
- Mark 6 fields as optional (briefing: summary, thumbnail, sourceUrl; news: summary; ecosystem: types, summary)
- Optionally remove `article.author` default

### 2. `c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs`
**Status:** ✅ Already correct - mirrors Astro schemas exactly

### 3. `c:\Dev\Claude\MMTUK\src\content.config.ts`
**Status:** ✅ No changes needed - this is the source of truth

---

## Appendix: nullableStr() Helper

**Astro helper** (content.config.ts:6):
```typescript
const nullableStr = () => z.string().nullable().optional().transform(v => v ?? undefined);
```

**Behavior:**
- Accepts `string | null | undefined`
- Transforms `null` → `undefined` for Zod's `.optional()` compatibility
- Functionally means "this field can be omitted or empty"

**CMS equivalent:** `{"type": "string", "optional": True}`

---

## End of Report

**Next Steps:**
1. Review this audit with team
2. Implement Priority 1 & 2 fixes in schemas.py
3. Run validation test suite
4. Proceed to Phase 2 Task #6 (Validation Hardening)
