"""
Categorise site images by site section and page section for the media library.

Groups responsive variants (e.g. image-p-500.avif) under their base image and
assigns each image group to a site section / subsection based on directory and
filename patterns.
"""

import re

# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------
# Each section has an id, display name, and a list of subsections.
# Each subsection has a name and a list of filename patterns (case-insensitive
# substring matches against the *base* filename, i.e. after stripping the
# responsive suffix).
#
# 'directory' is an optional filter — if set, the image must live in that
# subdirectory of public/images/ to match.
# ---------------------------------------------------------------------------

SITE_SECTIONS = [
    {
        'id': 'research',
        'name': 'Research',
        'subsections': [
            {'name': 'Hero', 'patterns': ['briefing-room']},
            {'name': 'Policy Cards', 'patterns': [
                'adult-education', 'central-london-banks', 'report-writing',
                'Report_IMG', 'financial-charts',
            ]},
            {'name': 'Briefing Thumbnails', 'patterns': [
                'nature-of-money', 'income-security', 'symmetry-that-blinds',
                'question-about-economics',
            ]},
            {'name': 'Newsroom', 'patterns': ['newsroom']},
        ],
    },
    {
        'id': 'education',
        'name': 'Education',
        'subsections': [
            {'name': 'Hero', 'patterns': ['hands-up']},
            {'name': 'Ask MMTUK', 'patterns': ['Ask-a-question']},
            {'name': 'Library', 'patterns': ['Library']},
            {'name': 'Events & Lectures', 'patterns': [
                'events-lecture', 'events-online-workshop',
            ]},
        ],
    },
    {
        'id': 'community',
        'name': 'Community',
        'subsections': [
            {'name': 'Hero', 'patterns': ['Local-events']},
            {'name': 'Discord', 'patterns': ['MMTUK-Discord', '84285bd93b0d']},
            {'name': 'Local Groups', 'directory': 'local-groups'},
            {'name': 'Events', 'patterns': [
                'bill-mitchell-event', 'pintonomics', 'scotland-festival',
            ]},
            {'name': 'Locations', 'patterns': [
                'brighton-pavilion', 'london-westminster', 'cardiff-castle',
                'edinburgh-castle',
            ]},
        ],
    },
    {
        'id': 'about',
        'name': 'About Us',
        'subsections': [
            {'name': 'Hero', 'patterns': ['About-Us', 'UK-Sectoral-balances']},
            {'name': 'Team Photos', 'directory': 'bios'},
        ],
    },
    {
        'id': 'join',
        'name': 'Join',
        'subsections': [
            {'name': 'Hero', 'patterns': ['Join']},
            {'name': 'Parallax People', 'patterns': [
                'senior-lady-coat', 'senior-lady', 'senior-man-books',
                'senior-man', 'young-man', 'female-professional',
                'female-student', 'sharp-person-outline',
            ]},
        ],
    },
    {
        'id': 'donate',
        'name': 'Donate',
        'subsections': [
            {'name': 'Hero', 'patterns': ['Donate', 'matt-seymour']},
            {'name': 'Cards', 'patterns': [
                'envelopes', 'diana-light',
            ]},
            {'name': 'Icons', 'patterns': ['gift', 'owl']},
        ],
    },
    {
        'id': 'homepage',
        'name': 'Homepage',
        'subsections': [
            {'name': 'Slider & Navigation', 'patterns': [
                'Home', 'Our-Work', 'News', 'marcos-luiz', 'yp-hero',
            ]},
            {'name': 'Feature Images', 'patterns': [
                'relume', 'ecosystem',
            ]},
        ],
    },
]

# Shared / catch-all section (added programmatically for unmatched images)
SHARED_SECTION = {
    'id': 'shared',
    'name': 'Shared / Site Assets',
    'subsections': [
        {'name': 'Logos & Branding', 'patterns': [
            'Logo', 'mmtuk-logo', 'favicon', 'webclip', 'og-image',
        ]},
        {'name': 'Icons & Placeholders', 'patterns': [
            'checkbox-check', 'placeholder', 'Placeholder', 'Image.svg',
            'interaction-icon', 'job-guarantee-hero',
        ]},
        {'name': 'Backgrounds', 'patterns': ['Webflow-Background']},
    ],
}

# Regex to detect Webflow responsive variant suffixes
_RESPONSIVE_RE = re.compile(r'-p-(\d+(?:x\d+)?(?:q\d+)?)\.(avif|png|jpg|jpeg|webp)$', re.IGNORECASE)


def _strip_responsive_suffix(filename):
    """
    Strip the Webflow responsive variant suffix from a filename.
    Returns (base_filename, is_variant).

    Examples:
        'briefing-room-p-500.avif'  -> ('briefing-room.avif', True)
        'briefing-room.avif'        -> ('briefing-room.avif', False)
        'Ask-a-question-p-130x130q80.avif' -> ('Ask-a-question.avif', True)
    """
    m = _RESPONSIVE_RE.search(filename)
    if m:
        base = filename[:m.start()] + '.' + m.group(2)
        return base, True
    return filename, False


def _get_image_subdir(web_path):
    """
    Extract the subdirectory from a web path like /images/bios/photo.avif.
    Returns '' for root images, 'bios' for /images/bios/*, etc.
    """
    # web_path is like /images/bios/photo.avif
    parts = web_path.strip('/').split('/')
    if len(parts) > 2:
        # e.g. ['images', 'bios', 'photo.avif'] -> 'bios'
        return parts[1]
    return ''


def _matches_subsection(base_filename, subdir, subsection):
    """Check if an image matches a subsection's criteria."""
    # Directory match
    if 'directory' in subsection:
        return subdir == subsection['directory']

    # Pattern match (case-insensitive substring)
    patterns = subsection.get('patterns', [])
    base_lower = base_filename.lower()
    for pattern in patterns:
        if pattern.lower() in base_lower:
            return True
    return False


def _group_responsive_variants(images):
    """
    Group images by their base name, collapsing responsive variants.

    Returns a list of dicts:
    [
        {
            'primary': <image_dict>,       # the base image (or largest variant if no base)
            'variants': [<image_dict>, ...],  # responsive variants
            'variant_count': int,
            'base_filename': str,
            'total_size': int,
        },
        ...
    ]
    """
    groups = {}  # base_filename -> {'primary': img, 'variants': [], 'all': []}

    for img in images:
        base, is_variant = _strip_responsive_suffix(img['filename'])
        # Include subdir in key to avoid collisions between dirs
        subdir = _get_image_subdir(img['web_path'])
        key = f'{subdir}/{base}' if subdir else base

        if key not in groups:
            groups[key] = {'primary': None, 'variants': [], 'all': []}

        groups[key]['all'].append(img)

        if not is_variant:
            groups[key]['primary'] = img
        else:
            groups[key]['variants'].append(img)

    result = []
    for key, group in groups.items():
        # If there's no non-variant base, pick the largest variant as primary
        if group['primary'] is None and group['all']:
            group['all'].sort(key=lambda x: x['size'], reverse=True)
            group['primary'] = group['all'][0]
            group['variants'] = group['all'][1:]
        elif group['primary']:
            # Ensure primary isn't also in variants
            primary_path = group['primary']['web_path']
            group['variants'] = [v for v in group['variants'] if v['web_path'] != primary_path]

        total_size = sum(img['size'] for img in group['all'])

        result.append({
            'primary': group['primary'],
            'variants': sorted(group['variants'], key=lambda x: x['size']),
            'variant_count': len(group['variants']),
            'base_filename': group['primary']['filename'] if group['primary'] else key.split('/')[-1],
            'total_size': total_size,
        })

    # Sort by filename
    result.sort(key=lambda x: x['base_filename'].lower())
    return result


def categorise_images(images):
    """
    Categorise a flat list of images (from list_images()) into a hierarchical
    structure organised by site section and page subsection.

    Returns a list of section dicts:
    [
        {
            'id': 'research',
            'name': 'Research',
            'image_count': 14,
            'subsections': [
                {
                    'name': 'Hero',
                    'groups': [<image_group>, ...],  # from _group_responsive_variants
                },
                ...
            ],
        },
        ...
    ]
    """
    # First, group responsive variants
    grouped = _group_responsive_variants(images)

    # Track which groups have been assigned
    assigned = set()  # indices into grouped

    sections = []

    all_sections = SITE_SECTIONS + [SHARED_SECTION]

    for section_def in all_sections:
        section = {
            'id': section_def['id'],
            'name': section_def['name'],
            'image_count': 0,
            'subsections': [],
        }

        for sub_def in section_def['subsections']:
            sub = {
                'name': sub_def['name'],
                'groups': [],
            }

            for idx, group in enumerate(grouped):
                if idx in assigned:
                    continue

                primary = group['primary']
                if not primary:
                    continue

                subdir = _get_image_subdir(primary['web_path'])
                base_filename = group['base_filename']

                if _matches_subsection(base_filename, subdir, sub_def):
                    sub['groups'].append(group)
                    assigned.add(idx)

            if sub['groups']:
                section['subsections'].append(sub)
                section['image_count'] += len(sub['groups'])

        if section['subsections']:
            sections.append(section)

    # Collect any remaining unassigned images into "Other"
    unassigned_groups = [g for idx, g in enumerate(grouped) if idx not in assigned]
    if unassigned_groups:
        # Check if Shared section already exists
        shared = next((s for s in sections if s['id'] == 'shared'), None)
        if shared:
            shared['subsections'].append({
                'name': 'Other',
                'groups': unassigned_groups,
            })
            shared['image_count'] += len(unassigned_groups)
        else:
            sections.append({
                'id': 'shared',
                'name': 'Shared / Site Assets',
                'image_count': len(unassigned_groups),
                'subsections': [{
                    'name': 'Other',
                    'groups': unassigned_groups,
                }],
            })

    return sections
