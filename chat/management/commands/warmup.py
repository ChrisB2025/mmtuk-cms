"""
Pre-warm expensive resources at startup to avoid slow first requests.

Clones the GitHub repo (if not already present) so that content creation
doesn't need to clone during an HTTP request.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pre-warm repo clone and schema cache for faster first requests.'

    def handle(self, *args, **options):
        # Pre-clone the repo (persists on disk across gunicorn workers)
        try:
            from chat.services.git_service import ensure_repo
            ensure_repo()
            self.stdout.write(self.style.SUCCESS('Repo clone ready.'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Repo warmup failed (non-fatal): {e}'))
