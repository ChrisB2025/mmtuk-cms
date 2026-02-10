"""
Management command to ensure all users have a UserProfile.
Creates missing profiles with 'contributor' role.
Optionally creates an admin user from environment variables.
"""

import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Ensure all users have a UserProfile. Create admin from env vars if set.'

    def handle(self, *args, **options):
        # Create profiles for users who don't have one
        users_without = User.objects.filter(profile__isnull=True)
        count = 0
        for user in users_without:
            UserProfile.objects.create(user=user, role='contributor')
            count += 1

        if count:
            self.stdout.write(self.style.SUCCESS(f'Created {count} missing UserProfile(s).'))
        else:
            self.stdout.write('All users already have profiles.')

        # Create admin from env vars if provided
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        admin_email = os.environ.get('ADMIN_EMAIL', '')

        if admin_username and admin_password:
            user, created = User.objects.get_or_create(
                username=admin_username,
                defaults={
                    'email': admin_email,
                    'is_staff': True,
                    'is_superuser': True,
                },
            )
            if created:
                user.set_password(admin_password)
                user.save()
                UserProfile.objects.get_or_create(user=user, defaults={'role': 'admin'})
                self.stdout.write(self.style.SUCCESS(f'Created admin user: {admin_username}'))
            else:
                # Ensure profile exists and is admin
                profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'admin'})
                if profile.role != 'admin':
                    profile.role = 'admin'
                    profile.save()
                self.stdout.write(f'Admin user "{admin_username}" already exists.')
