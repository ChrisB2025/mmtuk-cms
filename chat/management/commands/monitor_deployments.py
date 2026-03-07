"""
Management command stub — deployment monitoring is no longer needed.

Content is now served directly from the Django database. There are no
separate Astro deployments to track.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Monitor deployments (deprecated — no separate Astro deploys)'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'This command is deprecated. Content is now served directly '
                'from the database — no separate deployments to monitor.'
            )
        )
