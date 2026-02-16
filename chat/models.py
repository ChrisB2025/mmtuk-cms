import uuid

from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200, default='New conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    discarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} ({self.user.username})'


class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role}: {self.content[:60]}'


class ContentAuditLog(models.Model):
    """Audit trail for content create/edit/delete actions with redirect tracking."""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('edit', 'Edit'),
        ('delete', 'Delete'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.CharField(max_length=20)
    slug = models.CharField(max_length=300)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    git_commit_sha = models.CharField(max_length=40, blank=True, default='')
    changes_summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    # Redirect tracking for deleted content (SEO preservation)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='When content was deleted')
    redirect_target = models.CharField(
        max_length=500, blank=True, default='',
        help_text='URL path to redirect deleted content (e.g., /articles or /articles/category). Empty for intentional 404.'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'deleted_at']),  # For finding deleted content with redirects
        ]

    def __str__(self):
        return f'{self.action} {self.content_type}/{self.slug} by {self.user}'

    def get_source_path(self):
        """Get the original URL path for deleted content."""
        # Map content types to URL paths
        content_type_paths = {
            'article': '/articles',
            'news': '/news',
            'briefing': '/briefings',
            'local_event': '/local-events',
            'local_news': '/local-news',
            'bio': '/about',
            'ecosystem': '/ecosystem',
            'local_group': '/local-groups',
        }
        base_path = content_type_paths.get(self.content_type, f'/{self.content_type}')
        return f'{base_path}/{self.slug}'


class ContentDraft(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='drafts',
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='drafts')
    content_type = models.CharField(max_length=20)
    title = models.CharField(max_length=300)
    slug = models.CharField(max_length=300)
    frontmatter_json = models.JSONField(default=dict)
    body_markdown = models.TextField(blank=True, default='')
    image_path = models.CharField(max_length=500, blank=True, default='')
    image_data = models.BinaryField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_drafts',
    )
    review_feedback = models.TextField(blank=True, default='')
    git_commit_sha = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.content_type}: {self.title} ({self.get_status_display()})'


class DeploymentLog(models.Model):
    """Track Railway deployment status for published changes."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deployment_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    commit_sha = models.CharField(max_length=40, blank=True, default='')
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='deployments')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Deployment {self.deployment_id[:8]} - {self.get_status_display()}'
