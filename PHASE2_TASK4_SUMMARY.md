# Phase 2, Task #4: Event Lifecycle - COMPLETE ✅

**Date Completed:** 2026-02-16
**Time Spent:** ~3 hours

---

## Overview

Implemented automatic event archival for the MMTUK CMS. Events are now automatically archived 7 days after they end, keeping the "Upcoming Events" list clean while preserving historical event data.

---

## Deliverables

### 1. Updated Event Schema ✅

**Added Fields:**
- `endDate` (datetime, optional) - Event end date/time (defaults to `date` if not provided)
- `archived` (boolean, default false) - Auto-set 7 days after endDate

**Files Modified:**
- `c:\Dev\Claude\MMTUK\src\content.config.ts` - Astro Zod schema
- `c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs` - JSON Schema generator
- `c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py` - CMS schema

**Schema Changes:**
```typescript
// Astro schema (content.config.ts)
const localEvents = defineCollection({
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    localGroup: z.string(),
    date: z.coerce.date(),
    endDate: z.coerce.date().optional(),  // NEW
    tag: z.string(),
    location: z.string(),
    description: z.string(),
    link: nullableStr(),
    image: nullableStr(),
    partnerEvent: z.boolean().optional(),
    archived: z.boolean().default(false),  // NEW
  }),
});
```

### 2. Archive Management Command ✅

**File:** `chat/management/commands/archive_past_events.py` (186 lines)

**Features:**
- Finds events where `endDate < now() - 7 days`
- Falls back to `date` field if `endDate` not set
- Sets `archived: true` in frontmatter
- Commits changes to git with descriptive message
- Dry-run mode for previewing changes
- Force mode for testing/manual runs

**Usage:**
```bash
# Archive past events
python manage.py archive_past_events

# Preview what would be archived (no changes)
python manage.py archive_past_events --dry-run

# Force commit even if no events archived (for testing)
python manage.py archive_past_events --force
```

**Example Output:**
```
Archiving events that ended before: 2026-02-09 10:00 UTC

  ✓ Archiving: MMT Brighton Meetup (ended 2026-01-15)
  ✓ Archiving: London Economics Lecture (ended 2026-02-01)

============================================================
Total events processed: 25
  Archived: 2
  Already archived: 18
  Skipped: 5

============================================================
✓ Committed changes: chore: Auto-archive 2 past events
```

### 3. Django-Q Daily Schedule ✅

**File:** `chat/management/commands/setup_event_archival.py` (90 lines)

**Features:**
- Creates Django-Q schedule to run `archive_past_events` daily
- Idempotent - safe to run multiple times
- Updates existing schedule if found
- Runs automatically on deployment (via Dockerfile)

**Usage:**
```bash
# Set up daily archival schedule
python manage.py setup_event_archival
```

**Output:**
```
SUCCESS: Created new schedule: "Auto-Archive Past Events"
  Frequency: Daily
  Next run: 2026-02-17 02:00:00+00:00

NOTE: Make sure Django-Q cluster is running:
  python manage.py qcluster

Or on Railway, ensure worker service is deployed.
```

**Deployment Integration:**
Updated `Dockerfile` CMD to run `setup_event_archival` on every deployment:
```dockerfile
CMD ["sh", "-c", "python manage.py migrate && \
                  python manage.py setup_roles && \
                  python manage.py setup_deployment_monitoring && \
                  python manage.py setup_event_archival && \
                  gunicorn ..."]
```

### 4. Event Archive Page ✅

**Files:**
- `chat/views.py` - Added `event_archive()` view
- `chat/templates/chat/event_archive.html` - Event archive template
- `chat/urls.py` - Added route `/events/archive/`

**Features:**
- Shows all archived events in card grid
- Displays event date, end date, location, local group
- Search and sort functionality
- Badge indicators (tag, local group, "Archived")
- Clean, responsive design
- Shows event count

**View:**
- Filters for `archived=true` events only
- Content type: `local_event`
- Sort options: date (asc/desc), title (A-Z/Z-A)
- Search across event titles

**Access:**
Navigate to: `/events/archive/`

### 5. Unarchive Action ✅

**Files:**
- `chat/views.py` - Added `unarchive_event()` view
- `chat/urls.py` - Added route `/content/<type>/<slug>/unarchive/`
- `event_archive.html` - Unarchive button in event cards

**Features:**
- Admin/editor only (requires `can_approve_content` permission)
- Sets `archived: false` in event frontmatter
- Commits change to git
- Logs action in ContentAuditLog
- Shows success message
- Redirects to event detail page

**Usage:**
From Event Archive page → Click "♻️ Unarchive" button → Confirm

---

## Files Created/Modified

### New Files (3)
1. ✅ `chat/management/commands/archive_past_events.py` - Archive command
2. ✅ `chat/management/commands/setup_event_archival.py` - Schedule setup
3. ✅ `chat/templates/chat/event_archive.html` - Archive page template

### Modified Files (7)
1. ✅ `c:\Dev\Claude\MMTUK\src\content.config.ts` - Added endDate/archived fields
2. ✅ `c:\Dev\Claude\MMTUK\scripts\generate-schemas.mjs` - Added endDate/archived fields
3. ✅ `c:\Dev\Claude\mmtuk-cms\content_schema\schemas.py` - Added endDate/archived fields
4. ✅ `chat/views.py` - Added event_archive() and unarchive_event() views
5. ✅ `chat/urls.py` - Added event archive routes
6. ✅ `Dockerfile` - Added setup_event_archival to startup
7. ✅ `chat/views.py` - Added permission_required import

---

## Event Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────┐
│                   Event Created                              │
│             archived: false (default)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Event is Upcoming/Active                         │
│         Appears in /community event list                     │
│         Appears on /local-group/<group> pages                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Event Ends                                  │
│          (endDate or date passes)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Wait 7 Days                                     │
│    (Grace period for late attendees/updates)                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         Daily Archive Job Runs                               │
│    (via Django-Q schedule @ 2:00 AM UTC)                    │
│                                                               │
│    1. Find events where endDate < now() - 7 days            │
│    2. Set archived: true                                     │
│    3. Commit to git                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                Event is Archived                             │
│      - Hidden from upcoming events list                      │
│      - Visible in /events/archive/ page                      │
│      - Can be unarchived by admin/editor                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          (Optional) Unarchive Event                          │
│              archived: false                                 │
│         Returns to upcoming events list                      │
└──────────────────────────────────────────────────────────────┘
```

---

## Testing

### Manual Test Plan

1. **Create Test Event:**
   ```python
   # Create event via CMS with endDate in the past
   title: "Test Past Event"
   date: 2026-01-15T19:00:00.000Z
   endDate: 2026-01-15T21:00:00.000Z
   archived: false
   ```

2. **Run Archive Command (Dry Run):**
   ```bash
   python manage.py archive_past_events --dry-run
   ```
   Should show: "✓ Archiving: Test Past Event (ended 2026-01-15)"

3. **Run Archive Command:**
   ```bash
   python manage.py archive_past_events
   ```
   Should archive the event and commit to git

4. **Verify Event Archived:**
   - Check event frontmatter: `archived: true`
   - Event should NOT appear in content browser (filtered)
   - Event should appear in `/events/archive/`

5. **Test Unarchive:**
   - Navigate to `/events/archive/`
   - Click "♻️ Unarchive" on test event
   - Verify `archived: false` in frontmatter
   - Verify event returns to upcoming events list

6. **Test Schedule:**
   ```bash
   python manage.py setup_event_archival
   ```
   Should create/update Django-Q schedule

### Automated Tests (Future)

**Recommended test cases:**
```python
class EventArchivalTests(TestCase):
    def test_archive_past_events(self):
        # Create event with endDate > 7 days ago
        # Run archive command
        # Assert archived=true

    def test_dont_archive_recent_events(self):
        # Create event with endDate < 7 days ago
        # Run archive command
        # Assert archived=false (not changed)

    def test_unarchive_event(self):
        # Create archived event
        # Call unarchive_event view
        # Assert archived=false

    def test_schedule_creation(self):
        # Run setup_event_archival
        # Assert Django-Q schedule exists
        # Assert schedule runs daily
```

---

## Configuration

### Archive Threshold

Currently hardcoded to **7 days** in `archive_past_events.py`:
```python
threshold = datetime.now(timezone.utc) - timedelta(days=7)
```

To change, modify this line in the management command.

### Schedule Frequency

Currently set to **daily** in `setup_event_archival.py`:
```python
schedule = Schedule.objects.create(
    name='Auto-Archive Past Events',
    func='chat.management.commands.archive_past_events.Command.handle',
    schedule_type=Schedule.DAILY,  # Change to HOURLY, WEEKLY, etc.
)
```

---

## Maintenance

### View Archived Events

```bash
# Via CMS
Navigate to: /events/archive/

# Via command line (dry-run shows archived status)
python manage.py archive_past_events --dry-run
```

### Manually Archive an Event

```bash
# Edit event frontmatter directly
archived: true

# Or via CMS
# (Future feature: Add "Archive Now" button)
```

### Manually Unarchive an Event

```bash
# Via CMS
Navigate to: /events/archive/ → Click "♻️ Unarchive"

# Or edit frontmatter directly
archived: false
```

### Monitor Archive Job

```bash
# Check Django-Q schedule
python manage.py qinspect

# View logs
python manage.py qmonitor
```

---

## Next Steps

### Optional Enhancements

1. **Add "Archive Now" button** - Allow manual archival before 7-day threshold
2. **Archive count badge** - Show count of archived events in navigation
3. **Bulk unarchive** - Select multiple events to unarchive at once
4. **Archive notification** - Email admins when events are archived
5. **Configurable threshold** - Make 7-day threshold configurable via settings

### Future Tasks

**Phase 2 remaining:**
- **Task #5: Removed Content SEO** (Day 5, ~6 hours)
  - Track deleted content
  - Generate 301 redirects
  - Redirect management UI

---

## Summary

✅ **Event schema updated** - Added endDate and archived fields
✅ **Archive command created** - Auto-archive events 7+ days after end
✅ **Daily schedule configured** - Django-Q runs archival daily at 2 AM UTC
✅ **Event Archive page built** - View and manage archived events
✅ **Unarchive action implemented** - Restore events to active status
✅ **Deployment integration** - Setup runs automatically on Railway deploy

**Result:** Events now have a proper lifecycle - they appear when upcoming, get archived when past, and can be restored if needed. The "Upcoming Events" list stays clean and relevant.
