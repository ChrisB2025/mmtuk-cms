"""
Management command stub — validation metrics are no longer tracked.

Astro schema validation has been replaced by Django model validation.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Validation metrics (deprecated — Django model validation replaces Astro schema)'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'Validation metrics are no longer tracked. '
                'Django model validation has replaced Astro schema validation.'
            )
        )
