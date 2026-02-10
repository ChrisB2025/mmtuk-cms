from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('editor', 'Editor'),
    ('group_lead', 'Group Lead'),
    ('contributor', 'Contributor'),
]

LOCAL_GROUP_CHOICES = [
    ('brighton', 'Brighton'),
    ('london', 'London'),
    ('oxford', 'Oxford'),
    ('pennines', 'Pennines'),
    ('scotland', 'Scotland'),
    ('solent', 'Solent'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='contributor')
    local_group = models.CharField(
        max_length=20,
        choices=LOCAL_GROUP_CHOICES,
        blank=True,
        default='',
        help_text='Required for group_lead role. Must match a localGroups slug.',
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    def can_publish_directly(self, content_type, local_group=None):
        """Check if user can publish this content type directly (no approval)."""
        role = self.role

        if role == 'admin':
            return True

        if role == 'editor':
            return content_type in (
                'article', 'briefing', 'news', 'local_event', 'local_news', 'ecosystem',
            )

        if role == 'group_lead':
            if content_type in ('local_event', 'local_news'):
                return local_group == self.local_group
            return False

        return False

    def can_create(self, content_type, local_group=None):
        """Check if user can create this content type at all (even as draft)."""
        role = self.role

        if role == 'admin':
            return True

        if role == 'editor':
            return content_type in (
                'article', 'briefing', 'news', 'local_event', 'local_news', 'ecosystem',
            )

        if role == 'group_lead':
            if content_type in ('local_event', 'local_news'):
                return True  # can create for any group, but only direct-publish for own
            return False

        if role == 'contributor':
            return content_type in (
                'article', 'briefing', 'news', 'local_event', 'local_news',
            )

        return False

    def can_approve(self, content_type=None, local_group=None):
        """Check if user can approve pending drafts."""
        role = self.role

        if role == 'admin':
            return True

        if role == 'editor':
            return True

        if role == 'group_lead':
            if local_group and local_group == self.local_group:
                return content_type in ('local_event', 'local_news', None)
            return False

        return False

    def can_edit(self, content_type=None, local_group=None):
        """Check if user can edit existing content."""
        role = self.role

        if role == 'admin':
            return True

        if role == 'editor':
            return True

        if role == 'group_lead':
            if content_type in ('local_event', 'local_news'):
                return local_group == self.local_group if local_group else True
            return False

        return False

    def can_delete(self, content_type=None, local_group=None):
        """Check if user can delete content."""
        return self.role in ('admin', 'editor')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
