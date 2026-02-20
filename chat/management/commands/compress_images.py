"""
Management command to compress and convert existing images to WebP in the site repo.

Converts PNG and JPEG images to WebP (lossy quality=82 for photos, lossless for
transparent images). Resizes images wider than 1200px. Updates frontmatter
references in .md files when filenames change (.png/.jpg → .webp).

AVIF and SVG files are skipped — already optimised or incompatible.

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
MAX_WIDTH = 1200


def _optimize_to_webp(path: Path) -> tuple[bytes, bool]:
    """
    Convert an image to optimized WebP.
    Returns (webp_bytes, has_transparency).
    """
    with Image.open(path) as img:
        # Resize if wider than MAX_WIDTH
        if img.width > MAX_WIDTH:
            ratio = MAX_WIDTH / img.width
            new_height = int(img.height * ratio)
            img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)

        output = io.BytesIO()
        has_transparency = img.mode in ('RGBA', 'LA')

        if has_transparency:
            img.save(output, format='WEBP', lossless=True)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output, format='WEBP', quality=82, method=6)

    return output.getvalue(), has_transparency


def _update_frontmatter_refs(content_dir: Path, old_web_path: str, new_web_path: str) -> list[str]:
    """
    Find and update frontmatter references in .md files.
    Returns list of changed file paths (relative to repo root).
    """
    changed = []
    for md_file in content_dir.rglob('*.md'):
        text = md_file.read_text(encoding='utf-8')
        if old_web_path in text:
            updated = text.replace(old_web_path, new_web_path)
            md_file.write_text(updated, encoding='utf-8')
            changed.append(md_file)
    return changed


class Command(BaseCommand):
    help = 'Compress and convert existing PNG/JPEG images to WebP'

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

        clone_dir = Path(settings.REPO_CLONE_DIR)
        images_dir = clone_dir / 'public' / 'images'
        content_dir = clone_dir / 'src' / 'content'

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
        files_changed = []  # Relative paths for git staging

        for img_path in candidates:
            rel = img_path.relative_to(clone_dir)
            before = img_path.stat().st_size

            try:
                webp_bytes, has_transparency = _optimize_to_webp(img_path)
                after = len(webp_bytes)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  {rel}  ERROR: {exc}'))
                skipped_count += 1
                continue

            # New path with .webp extension
            webp_path = img_path.with_suffix('.webp')
            webp_rel = webp_path.relative_to(clone_dir)

            saving = before - after
            pct = (saving / before * 100) if before > 0 else 0

            if saving <= 0:
                self.stdout.write(f'  {rel}  {_fmt(before)} — already optimal')
                total_before += before
                total_after += before
                skipped_count += 1
                continue

            total_before += before
            total_after += after
            compressed_count += 1

            # Web paths for frontmatter: /images/foo.png → /images/foo.webp
            old_web_path = '/' + str(rel).replace('public/', '', 1).replace('\\', '/')
            new_web_path = '/' + str(webp_rel).replace('public/', '', 1).replace('\\', '/')

            if dry_run:
                self.stdout.write(
                    f'  {rel} → {webp_rel.name}  {_fmt(before)} → {_fmt(after)}  '
                    f'({self.style.SUCCESS(f"-{_fmt(saving)} / -{pct:.0f}%")})'
                )
                # Check for frontmatter references
                if content_dir.exists():
                    for md_file in content_dir.rglob('*.md'):
                        text = md_file.read_text(encoding='utf-8')
                        if old_web_path in text:
                            md_rel = md_file.relative_to(clone_dir)
                            self.stdout.write(
                                f'    ↳ will update ref in {md_rel}'
                            )
            else:
                # Write WebP file
                webp_path.write_bytes(webp_bytes)
                files_changed.append(str(webp_rel).replace('\\', '/'))

                # Remove old file (if different path)
                if img_path != webp_path:
                    img_path.unlink()
                    files_changed.append(str(rel).replace('\\', '/'))

                # Update frontmatter references
                if content_dir.exists() and old_web_path != new_web_path:
                    changed_mds = _update_frontmatter_refs(content_dir, old_web_path, new_web_path)
                    for md_file in changed_mds:
                        md_rel = md_file.relative_to(clone_dir)
                        files_changed.append(str(md_rel).replace('\\', '/'))
                        self.stdout.write(f'    ↳ updated ref in {md_rel}')

                self.stdout.write(
                    f'  {rel} → {webp_rel.name}  {_fmt(before)} → {_fmt(after)}  '
                    f'({self.style.SUCCESS(f"-{_fmt(saving)} / -{pct:.0f}%")})'
                )

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
            # Deduplicate file paths
            unique_files = list(dict.fromkeys(files_changed))
            try:
                commit_locally(
                    files=unique_files,
                    commit_message=f'chore: Convert {compressed_count} image(s) to WebP (-{total_pct:.0f}%)',
                    author_name='MMTUK CMS Compression',
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Committed {len(unique_files)} file(s). '
                        f'Go to Review & Publish when ready to push to the live site.'
                    )
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'Commit failed: {exc}'))
        else:
            self.stdout.write(
                f'{len(files_changed)} file(s) changed. '
                f'Run with --commit to create a git commit, then Publish to go live.\n'
            )


def _fmt(size_bytes: int) -> str:
    """Format bytes as KB/MB string."""
    if size_bytes >= 1_000_000:
        return f'{size_bytes / 1_000_000:.1f} MB'
    if size_bytes >= 1_000:
        return f'{size_bytes / 1_000:.1f} KB'
    return f'{size_bytes} B'
