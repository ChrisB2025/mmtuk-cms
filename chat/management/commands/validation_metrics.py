"""
Management command to view validation metrics.

Usage:
    python manage.py validation_metrics           # View current metrics
    python manage.py validation_metrics --reset   # Reset metrics
"""

from django.core.management.base import BaseCommand
from chat.services.astro_validator import (
    get_validation_metrics,
    reset_validation_metrics
)


class Command(BaseCommand):
    help = 'View or reset validation metrics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset validation metrics',
        )

    def handle(self, *args, **options):
        if options['reset']:
            reset_validation_metrics()
            self.stdout.write(
                self.style.SUCCESS('✓ Validation metrics reset')
            )
            return

        # Display metrics
        metrics = get_validation_metrics()

        if not metrics:
            self.stdout.write(
                self.style.WARNING('No validation metrics available yet.')
            )
            self.stdout.write(
                'Metrics are tracked for 1 hour and reset automatically.'
            )
            return

        self.stdout.write(
            self.style.SUCCESS('\n=== Validation Metrics (Last Hour) ===\n')
        )

        # Calculate totals
        total_validations = sum(m['total'] for m in metrics.values())
        total_passed = sum(m['passed'] for m in metrics.values())
        total_failed = sum(m['failed'] for m in metrics.values())
        total_errors = sum(m['total_errors'] for m in metrics.values())

        # Overall stats
        self.stdout.write('Overall:')
        self.stdout.write(f'  Total validations: {total_validations}')
        self.stdout.write(f'  Passed: {total_passed} ({100.0 * total_passed / total_validations:.1f}%)')
        self.stdout.write(f'  Failed: {total_failed} ({100.0 * total_failed / total_validations:.1f}%)')
        self.stdout.write(f'  Total errors: {total_errors}')

        if total_failed > 0:
            self.stdout.write(f'  Average errors per failure: {total_errors / total_failed:.1f}')

        self.stdout.write('\n')

        # Per-content-type stats
        self.stdout.write('By Content Type:')
        for content_type, data in sorted(metrics.items()):
            total = data['total']
            passed = data['passed']
            failed = data['failed']
            errors = data['total_errors']

            self.stdout.write(f'\n  {content_type}:')
            self.stdout.write(f'    Total: {total}')
            self.stdout.write(
                f'    Passed: {passed} ({100.0 * passed / total:.1f}%)'
            )

            if failed > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'    Failed: {failed} ({100.0 * failed / total:.1f}%)'
                    )
                )
                self.stdout.write(
                    f'    Avg errors per failure: {errors / failed:.1f}'
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('    Failed: 0 (100% pass rate)')
                )

        self.stdout.write('\n')
