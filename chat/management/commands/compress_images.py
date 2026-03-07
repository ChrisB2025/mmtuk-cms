"""
Management command stub — compress_images no longer uses git.

Images are now managed via Django's MEDIA_ROOT. Use image_service.py for
optimization on upload.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Compress images (deprecated — images are optimized on upload)'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'This command is deprecated. Images are now optimized to WebP '
                'on upload via the CMS chat interface.'
            )
        )
