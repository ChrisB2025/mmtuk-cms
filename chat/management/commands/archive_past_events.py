"""
Management command to auto-archive past events.

Archives local events that ended more than 7 days ago.
Events with endDate specified use that; otherwise uses the start date.

Usage:
    python manage.py archive_past_events            # Archive past events
    python manage.py archive_past_events --dry-run  # Preview what would be archived
    python manage.py archive_past_events --force    # Force commit even if no events archived
"""

from django.core.management.base import BaseCommand
from datetime import datetime, timedelta, timezone
from pathlib import Path
import frontmatter

from chat.services.git_service import (
    ensure_repo,
    commit_locally,
    get_repo_path
)
from content_schema.schemas import CONTENT_TYPES


class Command(BaseCommand):
    help = 'Auto-archive local events that ended more than 7 days ago'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be archived without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force commit even if no events archived',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n=== DRY RUN MODE - No changes will be made ===\n')
            )

        # Ensure repo is up to date
        ensure_repo()
        repo_path = Path(get_repo_path())

        # Get events directory from schema
        events_schema = CONTENT_TYPES['local_event']
        events_dir = repo_path / events_schema['directory']

        if not events_dir.exists():
            self.stdout.write(
                self.style.ERROR(f'Events directory not found: {events_dir}')
            )
            return

        # Calculate threshold (7 days ago)
        threshold = datetime.now(timezone.utc) - timedelta(days=7)

        self.stdout.write(
            f'\nArchiving events that ended before: {threshold.strftime("%Y-%m-%d %H:%M %Z")}\n'
        )

        # Process all event files
        archived_count = 0
        already_archived = 0
        skipped_count = 0
        files_to_commit = []

        for event_file in sorted(events_dir.glob('*.md')):
            try:
                # Parse frontmatter
                with open(event_file, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)

                title = post.get('title', event_file.stem)
                slug = post.get('slug', event_file.stem)
                archived = post.get('archived', False)

                # Check if already archived
                if archived:
                    already_archived += 1
                    continue

                # Get event end date (use endDate if available, otherwise use date)
                end_date = post.get('endDate') or post.get('date')

                if not end_date:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  {slug}: No date found, skipping'
                        )
                    )
                    skipped_count += 1
                    continue

                # Convert to datetime if needed
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    except ValueError:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠️  {slug}: Invalid date format "{end_date}", skipping'
                            )
                        )
                        skipped_count += 1
                        continue
                elif hasattr(end_date, 'replace'):  # datetime.date object
                    end_date = datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc)

                # Check if past threshold
                if end_date < threshold:
                    # Archive this event
                    archived_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Archiving: {title} (ended {end_date.strftime("%Y-%m-%d")})'
                        )
                    )

                    if not dry_run:
                        # Update frontmatter
                        post['archived'] = True

                        # Write back to file
                        with open(event_file, 'w', encoding='utf-8') as f:
                            f.write(frontmatter.dumps(post))

                        # Track for git commit
                        files_to_commit.append(str(event_file.relative_to(repo_path)))

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Error processing {event_file.name}: {e}'
                    )
                )
                skipped_count += 1

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'\nTotal events processed: {archived_count + already_archived + skipped_count}')
        self.stdout.write(f'  Archived: {archived_count}')
        self.stdout.write(f'  Already archived: {already_archived}')
        self.stdout.write(f'  Skipped: {skipped_count}')

        # Commit changes
        if not dry_run and (archived_count > 0 or force):
            if archived_count > 0:
                message = f'chore: Auto-archive {archived_count} past event{"s" if archived_count != 1 else ""}'
            else:
                message = 'chore: Event archival check (no changes)'

            try:
                commit_locally(
                    files=files_to_commit,
                    message=message,
                    author_name='MMTUK CMS Auto-Archival'
                )
                self.stdout.write('\n' + '=' * 60)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✓ Committed changes: {message}'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n✗ Failed to commit: {e}'
                    )
                )
        elif dry_run:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  DRY RUN - No changes were committed'
                )
            )
        else:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  No events to archive'
                )
            )

        self.stdout.write('\n')
