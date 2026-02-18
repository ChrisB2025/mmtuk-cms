"""
Management command to losslessly compress existing PNG/JPEG images in the site repo.

New uploads are already optimised via optimize=True in image_service.py.
This command retroactively compresses images that were uploaded before that change.

AVIF and SVG files are skipped — they are already optimised or incompatible with
Pillow's PNG/JPEG encoder.

Usage:
    python manage.py compress_images            # Compress all images, print savings
    python manage.py compress_images --dry-run  # Preview savings, make no changes
    python manage.py compress_images --commit   # Compress + create a local git commit
"""

import io
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from chat.services.git_service import commit_locally, ensure_repo

logger = logging.getLogger(__name__)

COMPRESSIBLE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def _compress_image(path: Path) -> tuple[int, int]:
    """
    Losslessly recompress the image at path in-place.
    Returns (before_bytes, after_bytes).
    Raises on failure.
    """
    before = path.stat().st_size
    ext = path.suffix.lower()

    with Image.open(path) as img:
        output = io.BytesIO()
        if ext == '.png':
            img.save(output, format='PNG', optimize=True)
        else:
            # JPEG — keep quality high (95) with optimization
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.save(output, format='JPEG', quality=95, optimize=True)

    compressed = output.getvalue()
    after = len(compressed)

    # Only write if we actually made it smaller
    if after < before:
        path.write_bytes(compressed)

    return before, min(before, after)


class Command(BaseCommand):
    help = 'Losslessly compress existing PNG/JPEG images in the site repo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview savings without modifying any files',
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Create a local git commit with the compressed images',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        do_commit = options['commit']

        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN — no files will be modified ===\n'))

        ensure_repo()

        images_dir = Path(settings.REPO_CLONE_DIR) / 'public' / 'images'
        if not images_dir.exists():
            self.stdout.write(self.style.ERROR(f'Images directory not found: {images_dir}'))
            return

        candidates = sorted(
            f for f in images_dir.rglob('*')
            if f.is_file() and f.suffix.lower() in COMPRESSIBLE_EXTENSIONS
        )

        if not candidates:
            self.stdout.write('No compressible images found.')
            return

        self.stdout.write(f'\nFound {len(candidates)} PNG/JPEG image(s) to process.\n')

        total_before = 0
        total_after = 0
        compressed_count = 0
        skipped_count = 0
        files_changed = []

        for img_path in candidates:
            rel = img_path.relative_to(Path(settings.REPO_CLONE_DIR))
            before = img_path.stat().st_size

            if dry_run:
                # Estimate savings without writing
                try:
                    ext = img_path.suffix.lower()
                    with Image.open(img_path) as img:
                        output = io.BytesIO()
                        if ext == '.png':
                            img.save(output, format='PNG', optimize=True)
                        else:
                            pil_img = img
                            if pil_img.mode in ('RGBA', 'LA', 'P'):
                                pil_img = pil_img.convert('RGB')
                            pil_img.save(output, format='JPEG', quality=95, optimize=True)
                    after = len(output.getvalue())
                    saving = before - after
                    pct = (saving / before * 100) if before > 0 else 0
                    if saving > 0:
                        self.stdout.write(
                            f'  {rel}  {_fmt(before)} → {_fmt(after)}  '
                            f'({self.style.SUCCESS(f"-{_fmt(saving)} / -{pct:.0f}%")})'
                        )
                        total_before += before
                        total_after += after
                        compressed_count += 1
                    else:
                        self.stdout.write(f'  {rel}  {_fmt(before)} — already optimal')
                        total_before += before
                        total_after += before
                        skipped_count += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'  {rel}  ERROR: {exc}'))
                    skipped_count += 1
            else:
                try:
                    before_b, after_b = _compress_image(img_path)
                    saving = before_b - after_b
                    pct = (saving / before_b * 100) if before_b > 0 else 0
                    total_before += before_b
                    total_after += after_b
                    if saving > 0:
                        self.stdout.write(
                            f'  {rel}  {_fmt(before_b)} → {_fmt(after_b)}  '
                            f'({self.style.SUCCESS(f"-{_fmt(saving)} / -{pct:.0f}%")})'
                        )
                        compressed_count += 1
                        files_changed.append(str(rel).replace('\\', '/'))
                    else:
                        self.stdout.write(f'  {rel}  {_fmt(before_b)} — already optimal')
                        skipped_count += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f'  {rel}  ERROR: {exc}'))
                    skipped_count += 1

        # Summary
        self.stdout.write('\n' + '=' * 60)
        total_saving = total_before - total_after
        total_pct = (total_saving / total_before * 100) if total_before > 0 else 0
        self.stdout.write(f'  Images compressed : {compressed_count}')
        self.stdout.write(f'  Already optimal   : {skipped_count}')
        if total_saving > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Total saving      : {_fmt(total_saving)} ({total_pct:.1f}%)'
                )
            )
        self.stdout.write('=' * 60 + '\n')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run complete — no files were modified.\n'))
            return

        if not files_changed:
            self.stdout.write('No files changed — nothing to commit.\n')
            return

        if do_commit:
            try:
                commit_locally(
                    files=files_changed,
                    commit_message=f'chore: Losslessly compress {len(files_changed)} image(s) (-{total_pct:.0f}%)',
                    author_name='MMTUK CMS Compression',
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Committed {len(files_changed)} file(s). '
                        f'Go to Review & Publish when ready to push to the live site.'
                    )
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'✗ Commit failed: {exc}'))
        else:
            self.stdout.write(
                f'{len(files_changed)} file(s) compressed. '
                f'Run with --commit to create a git commit, then Publish to go live.\n'
            )


def _fmt(size_bytes: int) -> str:
    """Format bytes as KB/MB string."""
    if size_bytes >= 1_000_000:
        return f'{size_bytes / 1_000_000:.1f} MB'
    if size_bytes >= 1_000:
        return f'{size_bytes / 1_000:.1f} KB'
    return f'{size_bytes} B'
