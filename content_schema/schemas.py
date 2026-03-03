"""
Content type definitions and validation for the MMTUK Astro site.

Source of truth: src/content.config.ts in the MMTUK repo.
"""

import re
import math
from datetime import date, datetime


CONTENT_TYPES = {
    "article": {
        "name": "Article",
        "directory": "src/content/articles/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["title", "slug", "category", "author", "pubDate"],
        "fields": {
            "title": {"type": "string", "description": "Article title"},
            "slug": {
                "type": "string",
                "description": "URL path segment, lowercase with hyphens",
            },
            "category": {
                "type": "enum",
                "options": [
                    "Article", "Commentary", "Research",
                    "Core Ideas", "Core Insights", "But what about...?",
                ],
                "description": (
                    "Determines layout and page grouping. "
                    "Core Ideas/Core Insights use simplified layout. "
                    "'But what about...?' uses rebuttal layout."
                ),
            },
            "layout": {
                "type": "enum",
                "options": ["default", "simplified", "rebuttal"],
                "default": "default",
                "description": "Page layout template. Auto-set based on category if not specified.",
            },
            "sector": {"type": "string", "default": "Economics"},
            "author": {"type": "string", "default": "MMTUK"},
            "authorTitle": {"type": "string", "optional": True},
            "pubDate": {"type": "date", "description": "Publication date YYYY-MM-DD"},
            "readTime": {"type": "number", "default": 5, "description": "Estimated read time in minutes"},
            "summary": {"type": "string", "optional": True, "description": "Used in cards and meta descriptions"},
            "thumbnail": {"type": "string", "optional": True, "description": "Path in public/images/, e.g. /images/my-article.png"},
            "mainImage": {"type": "string", "optional": True, "description": "Larger hero image path"},
            "featured": {"type": "boolean", "default": False, "description": "Featured items appear first/larger"},
            "color": {"type": "string", "optional": True, "description": "Card accent color"},
        },
        "appears_on": ["/articles", "/education", "/research", "/index"],
        "route": "/articles/{slug}",
    },

    "briefing": {
        "name": "Briefing",
        "directory": "src/content/briefings/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["title", "slug", "author", "pubDate"],
        "fields": {
            "title": {"type": "string"},
            "slug": {"type": "string"},
            "author": {"type": "string"},
            "authorTitle": {"type": "string", "optional": True},
            "pubDate": {"type": "date"},
            "readTime": {"type": "number", "default": 5},
            "summary": {"type": "string", "optional": True},
            "thumbnail": {"type": "string", "optional": True, "description": "Card image path in public/images/"},
            "mainImage": {"type": "string", "optional": True},
            "featured": {"type": "boolean", "default": False},
            "draft": {"type": "boolean", "default": False, "description": "Draft briefings are filtered out of all pages"},
            "sourceUrl": {"type": "string", "optional": True, "description": "Original article URL (for Substack imports)"},
            "sourceTitle": {"type": "string", "optional": True},
            "sourceAuthor": {"type": "string", "optional": True},
            "sourcePublication": {"type": "string", "optional": True},
            "sourceDate": {"type": "date", "optional": True},
        },
        "appears_on": ["/research/briefings", "/research", "/index"],
        "route": "/research/briefings/{slug}",
        "notes": (
            "Briefings can be imported from Substack URLs. "
            "When a URL is provided, scrape the article content, "
            "download and convert the thumbnail to PNG, and populate source fields. "
            "IMPORTANT: Use only ## (h2) headings in body — never h3 (renders larger than h2 in Webflow CSS)."
        ),
    },

    "news": {
        "name": "News",
        "directory": "src/content/news/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["title", "slug", "date", "category"],
        "fields": {
            "title": {"type": "string"},
            "slug": {"type": "string"},
            "date": {"type": "date"},
            "category": {
                "type": "enum",
                "options": ["Announcement", "Event", "Press Release", "Update"],
            },
            "summary": {"type": "string", "optional": True},
            "thumbnail": {"type": "string", "optional": True},
            "mainImage": {"type": "string", "optional": True},
            "registrationLink": {"type": "string", "optional": True, "description": "External registration URL"},
        },
        "appears_on": ["/about-us"],
        "route": "/news/{slug}",
        "notes": "News items appear as accordion items on /about-us. There is no /news index page.",
    },

    "local_event": {
        "name": "Local Event",
        "directory": "src/content/localEvents/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["title", "slug", "localGroup", "date", "tag", "location", "description"],
        "fields": {
            "title": {"type": "string"},
            "slug": {"type": "string"},
            "localGroup": {
                "type": "enum",
                "options": ["brighton", "london", "oxford", "pennines", "scotland", "solent"],
                "description": "Must match an existing local group slug",
            },
            "date": {"type": "datetime", "description": "Event date and time in ISO format"},
            "endDate": {"type": "datetime", "optional": True, "description": "Event end date/time (defaults to date if not provided)"},
            "tag": {"type": "string", "description": "Category label, e.g. Lecture, Meetup, Festival, Workshop"},
            "location": {"type": "string", "description": "Venue name and address"},
            "description": {"type": "string", "description": "Short description for card display"},
            "link": {"type": "string", "optional": True, "description": "URL, internal or external"},
            "image": {"type": "string", "optional": True, "description": "Event card image path"},
            "partnerEvent": {"type": "boolean", "optional": True, "description": "Whether this is a partner event"},
            "archived": {"type": "boolean", "default": False, "description": "Auto-set 7 days after endDate"},
        },
        "appears_on": ["/community", "/local-group/{localGroup}"],
        "route": "No individual pages",
        "notes": "Events appear on /community and on relevant /local-group/ pages filtered by localGroup. Events are auto-archived 7 days after endDate.",
    },

    "local_news": {
        "name": "Local News",
        "directory": "src/content/localNews/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["heading", "slug", "text", "localGroup", "date"],
        "fields": {
            "heading": {"type": "string", "description": "Note: this field is called 'heading' not 'title'"},
            "slug": {"type": "string"},
            "text": {"type": "string", "description": "Summary text for card display"},
            "localGroup": {
                "type": "enum",
                "options": ["brighton", "london", "oxford", "pennines", "scotland", "solent"],
                "description": "Must match an existing local group slug",
            },
            "date": {"type": "date"},
            "link": {"type": "string", "optional": True},
            "image": {"type": "string", "optional": True},
        },
        "appears_on": ["/local-group/{localGroup}"],
        "route": "/local-group/{localGroup}/{slug}",
    },

    "bio": {
        "name": "Bio",
        "directory": "src/content/bios/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["name", "slug", "role"],
        "fields": {
            "name": {"type": "string", "description": "Full name with title, e.g. Dr Phil Armstrong"},
            "slug": {"type": "string"},
            "role": {
                "type": "string",
                "description": (
                    "Role title. Use 'Advisory Board Member' for advisory board. "
                    "Other roles go to Steering Committee."
                ),
            },
            "photo": {"type": "string", "optional": True, "description": "Path like /images/bios/Name.avif"},
            "linkedin": {"type": "string", "optional": True},
            "twitter": {"type": "string", "optional": True},
            "website": {"type": "string", "optional": True},
            "advisoryBoard": {"type": "boolean", "default": False},
        },
        "appears_on": ["/about-us", "/founders"],
        "route": "No individual pages",
        "notes": "Admin only. On /about-us, bios split into Steering Committee and Advisory Board.",
    },

    "ecosystem": {
        "name": "Ecosystem Entry",
        "directory": "src/content/ecosystem/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["name", "slug"],
        "fields": {
            "name": {"type": "string"},
            "slug": {"type": "string"},
            "country": {"type": "string", "default": "UK"},
            "types": {"type": "string_array", "optional": True, "description": "Taxonomy tags, e.g. ['all', 'offline-events']"},
            "summary": {"type": "string", "optional": True},
            "logo": {"type": "string", "optional": True},
            "website": {"type": "string", "optional": True},
            "twitter": {"type": "string", "optional": True},
            "facebook": {"type": "string", "optional": True},
            "youtube": {"type": "string", "optional": True},
            "discord": {"type": "string", "optional": True},
            "status": {
                "type": "enum",
                "options": ["Active", "Inactive", "Archived"],
                "default": "Active",
            },
        },
        "appears_on": ["/ecosystem"],
        "route": "/ecosystem/{slug}",
    },

    "local_group": {
        "name": "Local Group",
        "directory": "src/content/localGroups/",
        "filename_pattern": "{slug}.md",
        "required_fields": ["name", "slug", "title", "tagline"],
        "fields": {
            "name": {"type": "string", "description": "Group name (e.g., 'Brighton')"},
            "slug": {"type": "string", "description": "URL slug (e.g., 'brighton')"},
            "title": {"type": "string", "description": "Page title"},
            "tagline": {"type": "string", "description": "Short description"},
            "headerImage": {"type": "string", "default": "", "description": "Hero image path"},
            "leaderName": {"type": "string", "optional": True, "description": "Group leader name"},
            "leaderIntro": {"type": "string", "optional": True, "description": "Leader bio/intro text"},
            "discordLink": {"type": "string", "optional": True, "description": "Discord invite URL"},
            "active": {"type": "boolean", "default": True, "description": "Whether group is currently active"},
        },
        "appears_on": ["/community"],
        "route": "/local-group/{slug}",
        "notes": "Local groups are geographic chapters. Each has a dedicated page showing their events and news.",
    },
}


def generate_slug(title):
    """Generate a URL-safe slug from a title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug


def estimate_read_time(text):
    """Estimate read time in minutes (200 wpm average)."""
    words = len(text.split())
    return max(1, math.ceil(words / 200))


def format_date(d):
    """Format a date/datetime for YAML frontmatter."""
    if isinstance(d, datetime):
        return d.strftime('%Y-%m-%dT%H:%M:%S.000Z')
    if isinstance(d, date):
        return d.strftime('%Y-%m-%dT00:00:00.000Z')
    if isinstance(d, str):
        return d
    return str(d)


def auto_layout(category):
    """Determine article layout from category."""
    if category in ('Core Ideas', 'Core Insights'):
        return 'simplified'
    if category == 'But what about...?':
        return 'rebuttal'
    return 'default'


def validate_frontmatter(content_type, frontmatter):
    """
    Validate frontmatter against the schema for a content type.
    Returns (is_valid, errors_list).
    """
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        return False, [f'Unknown content type: {content_type}']

    errors = []
    fields = schema['fields']
    required = schema['required_fields']

    for field_name in required:
        if field_name not in frontmatter or frontmatter[field_name] in (None, ''):
            errors.append(f'Missing required field: {field_name}')

    for field_name, value in frontmatter.items():
        if field_name not in fields:
            continue
        if value is None:
            continue  # Optional field sanitized away
        field_def = fields[field_name]

        if field_def['type'] == 'enum' and 'options' in field_def:
            if value not in field_def['options']:
                errors.append(
                    f'{field_name}: "{value}" is not a valid option. '
                    f'Must be one of: {field_def["options"]}'
                )

        # Type checks
        if field_def['type'] in ('string', 'date', 'datetime') and not isinstance(value, str):
            errors.append(f'{field_name}: expected string, got {type(value).__name__}')
        if field_def['type'] == 'boolean' and not isinstance(value, bool):
            errors.append(f'{field_name}: expected boolean, got {type(value).__name__}')
        if field_def['type'] == 'number' and not isinstance(value, (int, float)):
            errors.append(f'{field_name}: expected number, got {type(value).__name__}')

    return len(errors) == 0, errors


def apply_defaults(content_type, frontmatter):
    """Apply default values for missing optional fields."""
    schema = CONTENT_TYPES.get(content_type)
    if not schema:
        return frontmatter

    fields = schema['fields']
    result = dict(frontmatter)

    for field_name, field_def in fields.items():
        if field_name not in result and 'default' in field_def:
            result[field_name] = field_def['default']

    # Auto-set article layout from category
    if content_type == 'article' and 'category' in result:
        if 'layout' not in frontmatter or not frontmatter.get('layout'):
            result['layout'] = auto_layout(result['category'])

    return result


PAGE_TYPES = {
    "privacy-policy": {
        "name": "Privacy Policy",
        "route": "/privacy-policy",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "body": {"type": "markdown", "label": "Body Content"},
                },
            }
        },
        "admin_only": False,
    },
    "terms-of-engagement": {
        "name": "Terms of Engagement",
        "route": "/terms-of-engagement",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "body": {"type": "markdown", "label": "Body Content"},
                },
            }
        },
        "admin_only": False,
    },
    "cookie-preferences": {
        "name": "Cookie Preferences",
        "route": "/cookie-preferences",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "intro": {"type": "markdown", "label": "Introduction (How we use cookies + Cookie categories)"},
                    "services_list": {"type": "markdown", "label": "Cookies and Services"},
                },
            }
        },
        "admin_only": False,
    },
    "site-config": {
        "name": "Site Config",
        "route": "(global)",
        "editor_url_name": "site_config_editor",
        "sections": {
            "settings": {
                "name": "Site Settings",
                "fields": {
                    "discord_url": {"type": "string", "label": "Discord Invite URL", "admin_only": True},
                    "stripe_links.supporter": {"type": "string", "label": "Stripe Link \u2014 Supporter (monthly)", "admin_only": True},
                    "stripe_links.founder": {"type": "string", "label": "Stripe Link \u2014 Founder (one-off)", "admin_only": True},
                    "stripe_links.patron": {"type": "string", "label": "Stripe Link \u2014 Patron (variable)", "admin_only": True},
                    "action_network_form_id": {"type": "string", "label": "Action Network Form ID", "admin_only": True},
                    "founder_scheme.current_count": {"type": "number", "label": "Founder Scheme \u2014 Current Count"},
                    "founder_scheme.target_count": {"type": "number", "label": "Founder Scheme \u2014 Target Count"},
                    "founder_scheme.deadline_iso": {"type": "string", "label": "Countdown Deadline (MM/DD/YYYY HH:mm:ss)"},
                    "founder_scheme.deadline_display": {"type": "string", "label": "Display Deadline (e.g. Sun 17 May 2026)"},
                    "founder_scheme.milestone_message": {"type": "string", "label": "Milestone Message"},
                    "announcement_bar.enabled": {"type": "boolean", "label": "Announcement Bar \u2014 Enabled"},
                    "announcement_bar.message": {"type": "string", "label": "Announcement Bar \u2014 Message"},
                    "announcement_bar.link": {"type": "string", "label": "Announcement Bar \u2014 Link URL"},
                },
            }
        },
        "admin_only": True,
    },
}

# Roles permitted to edit any page
PAGE_EDITOR_ROLES = {"admin", "editor"}

# Pages where only admin can access at all
ADMIN_ONLY_PAGES = {"site-config"}

# Field-level admin restrictions per page
ADMIN_ONLY_FIELDS = {
    "site-config": {
        "discord_url",
        "stripe_links.supporter",
        "stripe_links.founder",
        "stripe_links.patron",
        "action_network_form_id",
    },
}


def build_full_schema_prompt():
    """
    Build a detailed schema reference for the Claude system prompt.
    Returns a formatted string describing all content types.
    """
    lines = []
    for ct_key, ct in CONTENT_TYPES.items():
        lines.append(f"### {ct['name']} (`{ct_key}`)")
        lines.append(f"Directory: `{ct['directory']}`")
        lines.append(f"File pattern: `{ct['filename_pattern']}`")
        lines.append(f"Required fields: {', '.join(ct['required_fields'])}")
        if ct.get('route'):
            lines.append(f"Route: `{ct['route']}`")
        if ct.get('appears_on'):
            lines.append(f"Appears on: {', '.join(ct['appears_on'])}")
        if ct.get('notes'):
            lines.append(f"Notes: {ct['notes']}")

        lines.append("")
        lines.append("Fields:")
        for fname, fdef in ct['fields'].items():
            parts = [f"  - **{fname}**"]
            parts.append(f"(type: {fdef['type']})")
            if fdef.get('options'):
                parts.append(f"Options: {fdef['options']}")
            if fdef.get('default') is not None:
                parts.append(f"Default: `{fdef['default']}`")
            if fdef.get('optional'):
                parts.append("(optional)")
            if fdef.get('description'):
                parts.append(f"— {fdef['description']}")
            lines.append(' '.join(parts))

        lines.append("")
        lines.append("---")
        lines.append("")

    return '\n'.join(lines)
