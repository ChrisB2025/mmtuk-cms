"""
Management command to auto-archive past events.

Archives local events that ended more than 7 days ago.

Usage:
    python manage.py archive_past_events            # Archive past events
    python manage.py archive_past_events --dry-run  # Preview what would be archived
"""

from django.core.management.base import BaseCommand
from datetime import datetime, timedelta, timezone

from content.models import LocalEvent


class Command(BaseCommand):
    help = 'Auto-archive local events that ended more than 7 days ago'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be archived without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n=== DRY RUN MODE - No changes will be made ===\n')
            )

        threshold = (datetime.now(timezone.utc) - timedelta(days=7)).date()

        self.stdout.write(
            f'\nArchiving events that ended before: {threshold.strftime("%Y-%m-%d")}\n'
        )

        # Find non-archived events past the threshold
        events = LocalEvent.objects.filter(archived=False)
        archived_count = 0
        skipped_count = 0

        for event in events:
            end_date = event.end_date or event.date
            if not end_date:
                self.stdout.write(
                    self.style.WARNING(f'  -- {event.slug}: No date found, skipping')
                )
                skipped_count += 1
                continue

            if end_date < threshold:
                archived_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Archiving: {event.title} (ended {end_date.strftime("%Y-%m-%d")})'
                    )
                )
                if not dry_run:
                    event.archived = True
                    event.save(update_fields=['archived'])

        already_archived = LocalEvent.objects.filter(archived=True).count()

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'\nArchived: {archived_count}')
        self.stdout.write(f'Already archived: {already_archived}')
        self.stdout.write(f'Skipped: {skipped_count}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were made'))
        self.stdout.write('')
