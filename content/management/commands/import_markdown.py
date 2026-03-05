import re
from datetime import date, datetime
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)

# camelCase frontmatter key → snake_case model field
FIELD_MAP = {
    'authorTitle': 'author_title',
    'pubDate': 'pub_date',
    'readTime': 'read_time',
    'mainImage': 'main_image',
    'registrationLink': 'registration_link',
    'advisoryBoard': 'advisory_board',
    'headerImage': 'header_image',
    'leaderName': 'leader_name',
    'leaderIntro': 'leader_intro',
    'discordLink': 'discord_link',
    'localGroup': 'local_group',
    'endDate': 'end_date',
    'partnerEvent': 'partner_event',
    'sourceUrl': 'source_url',
    'sourceTitle': 'source_title',
    'sourceAuthor': 'source_author',
    'sourcePublication': 'source_publication',
    'sourceDate': 'source_date',
}

# Collection subdir → (Model, default status)
COLLECTIONS = {
    'localGroups': (LocalGroup, 'published'),
    'articles': (Article, 'published'),
    'briefings': (Briefing, 'published'),
    'news': (News, 'published'),
    'bios': (Bio, 'published'),
    'ecosystem': (EcosystemEntry, 'draft'),
    'localEvents': (LocalEvent, 'published'),
    'localNews': (LocalNews, 'published'),
}


def parse_markdown_file(filepath):
    """Parse a markdown file with YAML frontmatter into (frontmatter_dict, body_str)."""
    text = filepath.read_text(encoding='utf-8')
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', text, re.DOTALL)
    if not match:
        return None, text
    fm_text, body = match.groups()
    frontmatter = yaml.safe_load(fm_text) or {}
    return frontmatter, body.strip()


def normalize_date(value):
    """Convert various date formats to a Python date object."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        # Handle ISO format like "2026-01-26T00:00:00.000Z"
        cleaned = value.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            pass
        # Try simple date
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    return value


def map_fields(frontmatter):
    """Map camelCase frontmatter keys to snake_case model fields."""
    mapped = {}
    for key, value in frontmatter.items():
        field_name = FIELD_MAP.get(key, key)
        # Normalize None/null to empty string for string fields
        if value is None:
            value = ''
        mapped[field_name] = value
    return mapped


class Command(BaseCommand):
    help = 'Import markdown content files from the Astro site into Django models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-dir',
            default='c:/Dev/Claude/MMTUK/src/content',
            help='Path to Astro content directory',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without writing to database',
        )

    def handle(self, *args, **options):
        source_dir = Path(options['source_dir'])
        dry_run = options['dry_run']

        if not source_dir.exists():
            self.stderr.write(self.style.ERROR(f'Source directory not found: {source_dir}'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be made\n'))

        totals = {}

        # Import LocalGroups first (FK dependency)
        for collection_name, (model, default_status) in COLLECTIONS.items():
            collection_dir = source_dir / collection_name
            if not collection_dir.exists():
                self.stdout.write(self.style.WARNING(f'  Skipping {collection_name}: directory not found'))
                continue

            md_files = sorted(collection_dir.glob('*.md'))
            created = 0
            updated = 0
            skipped = 0

            for filepath in md_files:
                frontmatter, body = parse_markdown_file(filepath)
                if frontmatter is None:
                    self.stdout.write(self.style.WARNING(f'  Skipping {filepath.name}: no frontmatter'))
                    skipped += 1
                    continue

                fields = map_fields(frontmatter)
                slug = fields.get('slug', '')
                if not slug:
                    self.stdout.write(self.style.WARNING(f'  Skipping {filepath.name}: no slug'))
                    skipped += 1
                    continue

                # Add body and default status
                fields['body'] = body
                if 'status' not in fields:
                    fields['status'] = default_status

                # Handle EcosystemEntry: rename 'status' from frontmatter to 'activity_status'
                if model == EcosystemEntry and 'status' in frontmatter:
                    fields['activity_status'] = frontmatter['status'] or 'Active'
                    fields['status'] = default_status

                # Normalize date fields
                for date_field in ['pub_date', 'date', 'end_date', 'source_date']:
                    if date_field in fields and fields[date_field]:
                        fields[date_field] = normalize_date(fields[date_field])
                    elif date_field in fields and fields[date_field] == '':
                        fields.pop(date_field)

                # Handle types field (ecosystem) — may be array already or semicolon-separated string
                if 'types' in fields:
                    val = fields['types']
                    if isinstance(val, str):
                        fields['types'] = [t.strip() for t in val.split(';') if t.strip()]
                    elif isinstance(val, list):
                        # Flatten items that may contain semicolons
                        flat = []
                        for item in val:
                            if isinstance(item, str) and ';' in item:
                                flat.extend(t.strip() for t in item.split(';') if t.strip())
                            elif isinstance(item, str) and item.strip():
                                flat.append(item.strip())
                        fields['types'] = flat
                    elif not val:
                        fields['types'] = []

                # Resolve local_group FK by slug
                if 'local_group' in fields:
                    group_slug = fields['local_group']
                    if isinstance(group_slug, str) and group_slug:
                        try:
                            fields['local_group'] = LocalGroup.objects.get(slug=group_slug)
                        except LocalGroup.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f'  {filepath.name}: local_group "{group_slug}" not found, setting to null'
                            ))
                            fields['local_group'] = None
                    else:
                        fields['local_group'] = None

                # Remove any fields not on the model
                model_field_names = {f.name for f in model._meta.get_fields()}
                extra_keys = [k for k in fields if k not in model_field_names]
                for k in extra_keys:
                    fields.pop(k)

                if dry_run:
                    self.stdout.write(f'  Would import {collection_name}/{slug}')
                    created += 1
                    continue

                defaults = {k: v for k, v in fields.items() if k != 'slug'}
                _, was_created = model.objects.update_or_create(
                    slug=slug,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            totals[collection_name] = {'created': created, 'updated': updated, 'skipped': skipped}
            action = 'Would import' if dry_run else 'Imported'
            self.stdout.write(self.style.SUCCESS(
                f'{collection_name}: {created} created, {updated} updated, {skipped} skipped'
            ))

        # Summary
        self.stdout.write('\n--- Summary ---')
        total_items = 0
        for name, counts in totals.items():
            total = counts['created'] + counts['updated']
            total_items += total
            self.stdout.write(f'  {name}: {total} items')
        self.stdout.write(self.style.SUCCESS(f'\nTotal: {total_items} items'))
