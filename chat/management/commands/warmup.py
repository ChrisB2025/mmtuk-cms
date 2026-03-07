"""
Pre-warm expensive resources at startup.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-warm resources for faster first requests.'

    def handle(self, *args, **options):
        # Content is now in the database — no repo to clone.
        # Keep this command as a no-op for backward compatibility with start.sh.
        self.stdout.write(self.style.SUCCESS('Warmup complete (no-op — content is in the database).'))
