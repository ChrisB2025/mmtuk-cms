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
    "home": {
        "name": "Home",
        "route": "/",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "slides": {
                        "type": "object_array",
                        "label": "Hero Slides",
                        "item_fields": {
                            "tag": {"type": "string", "label": "Tag (e.g. Policy research)"},
                            "text": {"type": "string", "label": "Slide text / blurb"},
                            "link_href": {"type": "string", "label": "Link URL"},
                            "link_label": {"type": "string", "label": "Link label (visible text)"},
                        },
                    },
                },
            },
            "research_section": {
                "name": "Research Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                },
            },
            "education_section": {
                "name": "Education Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                },
            },
            "community_section": {
                "name": "Community Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                    "card_3_heading": {"type": "string", "label": "Card 3 Heading"},
                    "card_3_body": {"type": "string", "label": "Card 3 Body"},
                    "card_3_href": {"type": "string", "label": "Card 3 Link"},
                    "card_3_button_label": {"type": "string", "label": "Card 3 Button Label"},
                },
            },
            "testimonials": {
                "name": "Testimonials",
                "fields": {
                    "items": {
                        "type": "object_array",
                        "label": "Testimonial Items",
                        "item_fields": {
                            "quote": {"type": "string", "label": "Quote"},
                            "name": {"type": "string", "label": "Name"},
                            "title": {"type": "string", "label": "Title / Role"},
                        },
                    },
                },
            },
            "contact": {
                "name": "Contact",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
        },
        "admin_only": False,
    },
    "research": {
        "name": "Research",
        "route": "/research",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "policy_areas": {
                "name": "Policy Areas",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "job_guarantee": {
                "name": "Job Guarantee",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "feature_1": {"type": "string", "label": "Feature 1"},
                    "feature_2": {"type": "string", "label": "Feature 2"},
                    "feature_3": {"type": "string", "label": "Feature 3"},
                    "button_label": {"type": "string", "label": "Button Label"},
                    "button_href": {"type": "string", "label": "Button Link"},
                },
            },
            "zirp": {
                "name": "ZIRP",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "feature_1": {"type": "string", "label": "Feature 1"},
                    "feature_2": {"type": "string", "label": "Feature 2"},
                    "feature_3": {"type": "string", "label": "Feature 3"},
                    "wip_notice": {"type": "string", "label": "Work in Progress Notice"},
                },
            },
            "briefings": {
                "name": "MMT Briefings",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "tag_label": {"type": "string", "label": "Tag Label"},
                    "read_button_label": {"type": "string", "label": "Read Button Label"},
                    "view_all_label": {"type": "string", "label": "View All Label"},
                },
            },
            "approach": {
                "name": "Our Approach",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_3_heading": {"type": "string", "label": "Card 3 Heading"},
                    "card_3_body": {"type": "string", "label": "Card 3 Body"},
                    "card_4_heading": {"type": "string", "label": "Card 4 Heading"},
                    "card_4_body": {"type": "string", "label": "Card 4 Body"},
                    "card_5_heading": {"type": "string", "label": "Card 5 Heading"},
                    "card_5_body": {"type": "string", "label": "Card 5 Body"},
                },
            },
        },
        "admin_only": False,
    },
    "job-guarantee": {
        "name": "Job Guarantee",
        "route": "/job-guarantee",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "header": {
                "name": "Header",
                "fields": {
                    "page_title": {"type": "string", "label": "Page Title (H1)"},
                    "policy_type": {"type": "string", "label": "Policy Type Label"},
                },
            },
            "metadata": {
                "name": "Publication Metadata",
                "fields": {
                    "publication_date": {"type": "string", "label": "Publication Date"},
                    "download_url": {"type": "string", "label": "PDF Download URL"},
                    "video_url": {"type": "string", "label": "Vimeo Video URL"},
                },
            },
            "body": {
                "name": "Body Content",
                "fields": {
                    "content": {"type": "markdown", "label": "Body Content"},
                },
            },
        },
        "admin_only": False,
    },
    "education": {
        "name": "Education",
        "route": "/education",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "library": {
                "name": "MMTUK Library",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                    "coming_soon_label": {"type": "string", "label": "Coming Soon Label"},
                },
            },
            "what_is_mmt": {
                "name": "What is MMT?",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "paragraph_1": {"type": "string", "label": "Paragraph 1"},
                    "paragraph_2": {"type": "string", "label": "Paragraph 2"},
                },
            },
            "core_insights": {
                "name": "MMT Core Insights",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "items": {
                        "type": "object_array",
                        "label": "Accordion Items",
                        "item_fields": {
                            "title": {"type": "string", "label": "Title"},
                            "body": {"type": "string", "label": "Body"},
                            "link_href": {"type": "string", "label": "Read More Link"},
                        },
                    },
                },
            },
            "objections": {
                "name": "But what about...?",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "items": {
                        "type": "object_array",
                        "label": "Objection Items",
                        "item_fields": {
                            "title": {"type": "string", "label": "Title"},
                            "body": {"type": "string", "label": "Body"},
                            "link_href": {"type": "string", "label": "Read More Link"},
                        },
                    },
                },
            },
            "advisory_services": {
                "name": "Advisory Services",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "paragraph_1": {"type": "string", "label": "Paragraph 1"},
                },
            },
        },
        "admin_only": False,
    },
    "community": {
        "name": "Community",
        "route": "/community",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "local_groups": {
                "name": "Local Groups",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "events": {
                "name": "Upcoming Events",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "discord": {
                "name": "Discord CTA",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
        },
        "admin_only": False,
    },
    "about-us": {
        "name": "About Us",
        "route": "/about-us",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "news": {
                "name": "MMTUK News",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Read More Button Label"},
                },
            },
            "events": {
                "name": "MMTUK Events",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Learn More Button Label"},
                },
            },
            "steering_group": {
                "name": "Steering Group",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "order": {"type": "string_array", "label": "Display Order (one name per line)"},
                },
            },
            "advisory_board": {
                "name": "Advisory Board",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
        },
        "admin_only": False,
    },
    "donate": {
        "name": "Donate",
        "route": "/donate",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "founder_section": {
                "name": "Founder Member Scheme",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "body": {"type": "string", "label": "Body"},
                },
            },
            "founder_cta": {
                "name": "Founder CTA Card",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "plan_label": {"type": "string", "label": "Plan Label"},
                    "plan_amount": {"type": "string", "label": "Plan Amount"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "research_donations": {
                "name": "Research Donations",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                    "bullet_1": {"type": "string", "label": "Bullet 1"},
                    "bullet_2": {"type": "string", "label": "Bullet 2"},
                    "bullet_3": {"type": "string", "label": "Bullet 3"},
                },
            },
            "pricing": {
                "name": "Pricing Tiers",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "supporter_label": {"type": "string", "label": "Supporter Label"},
                    "supporter_amount": {"type": "string", "label": "Supporter Amount"},
                    "supporter_period": {"type": "string", "label": "Supporter Period"},
                    "supporter_button": {"type": "string", "label": "Supporter Button"},
                    "founder_label": {"type": "string", "label": "Founder Label"},
                    "founder_amount": {"type": "string", "label": "Founder Amount"},
                    "founder_period": {"type": "string", "label": "Founder Period"},
                    "founder_button": {"type": "string", "label": "Founder Button"},
                    "patron_label": {"type": "string", "label": "Patron Label"},
                    "patron_amount": {"type": "string", "label": "Patron Amount"},
                    "patron_period": {"type": "string", "label": "Patron Period"},
                    "patron_button": {"type": "string", "label": "Patron Button"},
                },
            },
            "thank_you": {
                "name": "Thank You",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                },
            },
        },
        "admin_only": False,
    },
    "founders": {
        "name": "Founders",
        "route": "/founders",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "subtitle": {"type": "string", "label": "Subtitle"},
                },
            },
            "feature_1": {
                "name": "Feature 1",
                "fields": {
                    "tag": {"type": "string", "label": "Tag"},
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "feature_2": {
                "name": "Feature 2 (Countdown)",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tag": {"type": "string", "label": "Tag"},
                    "date": {"type": "string", "label": "Deadline Date Label"},
                    "countdown_target": {"type": "string", "label": "Countdown Target (MM/DD/YYYY HH:mm:ss)"},
                    "tier_label": {"type": "string", "label": "Tier Label"},
                    "tier_description": {"type": "string", "label": "Tier Description"},
                    "tier_price": {"type": "string", "label": "Tier Price"},
                    "button_label": {"type": "string", "label": "Button Label"},
                    "form_success_message": {"type": "string", "label": "Form Success Message"},
                    "form_error_message": {"type": "string", "label": "Form Error Message"},
                },
            },
            "cta_section": {
                "name": "CTA Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "trust_label": {"type": "string", "label": "Trust Label"},
                    "tier_label": {"type": "string", "label": "Tier Label"},
                    "tier_description": {"type": "string", "label": "Tier Description"},
                    "tier_price": {"type": "string", "label": "Tier Price"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "testimonials": {
                "name": "Testimonials",
                "fields": {
                    "items": {
                        "type": "object_array",
                        "label": "Testimonial Items",
                        "item_fields": {
                            "quote": {"type": "string", "label": "Quote"},
                            "name": {"type": "string", "label": "Name"},
                            "role": {"type": "string", "label": "Role"},
                        },
                    },
                },
            },
            "faq": {
                "name": "FAQs",
                "fields": {
                    "heading": {"type": "string", "label": "Section Heading"},
                    "intro": {"type": "string", "label": "Intro Text"},
                    "items": {
                        "type": "object_array",
                        "label": "FAQ Items",
                        "item_fields": {
                            "question": {"type": "string", "label": "Question"},
                            "answer": {"type": "string", "label": "Answer"},
                        },
                    },
                    "contact_heading": {"type": "string", "label": "Contact Heading"},
                    "contact_intro": {"type": "string", "label": "Contact Intro"},
                },
            },
        },
        "admin_only": False,
    },
}

    "join": {
        "name": "Join",
        "route": "/join",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "join_section": {
                "name": "Join Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "subtitle": {"type": "string", "label": "Subtitle"},
                    "intro": {"type": "string", "label": "Intro Paragraph"},
                    "benefits": {"type": "string_array", "label": "Benefits List (one per line)"},
                },
            },
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
