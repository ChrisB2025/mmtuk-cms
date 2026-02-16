"""
Management command to set up periodic Railway deployment monitoring.

This command creates or updates a Django-Q schedule that runs
monitor_deployments every 5 minutes to poll Railway API for
deployment status updates.

Usage:
    python manage.py setup_deployment_monitoring

Idempotent - safe to run multiple times.
Intended to run:
- On Railway deployment (add to start.sh)
- Manually when setting up the CMS
"""

from django.core.management.base import BaseCommand
from django.db.utils import ProgrammingError, OperationalError


class Command(BaseCommand):
    help = 'Set up periodic Railway deployment monitoring via Django-Q'

    def handle(self, *args, **options):
        try:
            from django_q.models import Schedule
        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    '✗ django-q2 not installed. Install with: pip install django-q2'
                )
            )
            return

        schedule_name = 'Monitor Railway Deployments'

        # Check if Django-Q tables exist by trying to query
        try:
            # Check if schedule already exists
            existing = Schedule.objects.filter(name=schedule_name).first()
        except (ProgrammingError, OperationalError):
            self.stdout.write(
                self.style.WARNING(
                    'WARNING: Django-Q tables not found. Run migrations first:'
                )
            )
            self.stdout.write('  python manage.py migrate django_q')
            return

        if existing:
            # Update existing schedule
            existing.func = 'chat.management.commands.monitor_deployments.Command.handle'
            existing.schedule_type = Schedule.MINUTES
            existing.minutes = 5
            existing.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f'SUCCESS: Updated existing schedule: "{schedule_name}"'
                )
            )
            self.stdout.write(f'  Frequency: Every 5 minutes')
            self.stdout.write(f'  Next run: {existing.next_run}')
        else:
            # Create new schedule
            schedule = Schedule.objects.create(
                name=schedule_name,
                func='chat.management.commands.monitor_deployments.Command.handle',
                schedule_type=Schedule.MINUTES,
                minutes=5,
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'SUCCESS: Created new schedule: "{schedule_name}"'
                )
            )
            self.stdout.write(f'  Frequency: Every 5 minutes')
            self.stdout.write(f'  Next run: {schedule.next_run}')

        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                'NOTE: Make sure Django-Q cluster is running:'
            )
        )
        self.stdout.write('  python manage.py qcluster')
        self.stdout.write('')
        self.stdout.write('Or on Railway, ensure worker service is deployed.')
