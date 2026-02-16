"""
Management command to monitor pending Railway deployments.

This command polls the Railway API for deployment status updates and marks
DeploymentLog entries as success/failed/timeout accordingly.

Usage:
    python manage.py monitor_deployments [--max-age-hours 24]

Intended to run periodically (every 5-10 minutes) via:
- Django-Q scheduled task
- Cron job
- Railway cron trigger

Configuration:
    Requires RAILWAY_API_TOKEN and RAILWAY_PROJECT_ID in settings.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from chat.models import DeploymentLog
from chat.services.railway_service import get_deployment_status


class Command(BaseCommand):
    help = 'Monitor pending Railway deployments and update their status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=24,
            help='Maximum age in hours for pending deployments to monitor (default: 24)',
        )
        parser.add_argument(
            '--timeout-hours',
            type=int,
            default=1,
            help='Mark deployments as timeout if pending for longer than this (default: 1)',
        )

    def handle(self, *args, **options):
        max_age_hours = options['max_age_hours']
        timeout_hours = options['timeout_hours']

        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        timeout_cutoff = timezone.now() - timedelta(hours=timeout_hours)

        # Find pending deployments within the monitoring window
        pending = DeploymentLog.objects.filter(
            status='pending',
            started_at__gte=cutoff_time,
        ).order_by('started_at')

        if not pending.exists():
            self.stdout.write(self.style.SUCCESS('No pending deployments to monitor'))
            return

        self.stdout.write(f'Monitoring {pending.count()} pending deployment(s)...')

        success_count = 0
        failed_count = 0
        timeout_count = 0
        still_pending = 0

        for deployment in pending:
            # Check if deployment is too old (mark as timeout)
            if deployment.started_at < timeout_cutoff:
                deployment.status = 'timeout'
                deployment.completed_at = timezone.now()
                deployment.error_message = f'Deployment monitoring timed out after {timeout_hours} hour(s)'
                deployment.save()
                timeout_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⏱ Deployment {deployment.deployment_id[:8]}... timed out'
                    )
                )
                continue

            # Poll Railway API for status
            status, error_message = get_deployment_status(deployment.deployment_id)

            if status is None:
                # API error - skip for now, will retry next run
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠ Could not fetch status for {deployment.deployment_id[:8]}... (API error)'
                    )
                )
                continue

            if status == 'pending':
                # Still building/deploying
                still_pending += 1
                self.stdout.write(
                    f'  ⏳ Deployment {deployment.deployment_id[:8]}... still pending'
                )
                continue

            # Update deployment record
            deployment.status = status
            deployment.completed_at = timezone.now()
            if error_message:
                deployment.error_message = error_message
            deployment.save()

            if status == 'success':
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Deployment {deployment.deployment_id[:8]}... succeeded'
                    )
                )
            elif status == 'failed':
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Deployment {deployment.deployment_id[:8]}... failed: {error_message}'
                    )
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Summary ==='))
        self.stdout.write(f'  ✓ Succeeded: {success_count}')
        self.stdout.write(f'  ✗ Failed: {failed_count}')
        self.stdout.write(f'  ⏱ Timed out: {timeout_count}')
        self.stdout.write(f'  ⏳ Still pending: {still_pending}')

        if failed_count > 0:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    '⚠ Some deployments failed. Check Railway logs for details.'
                )
            )
