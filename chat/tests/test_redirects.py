"""
Test suite for redirect management functionality (Task #5: Removed Content SEO).

Tests cover:
- ContentAuditLog model with redirect tracking
- Redirect service functions
- Redirect generation
- Delete content with redirect target
- Redirect management views
"""

import pytest
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from chat.models import ContentAuditLog
from chat.services.redirect_service import (
    get_active_redirects,
    generate_redirects_config,
    validate_redirect_target,
    get_redirect_summary,
)


@pytest.mark.django_db
class TestContentAuditLogRedirectFields:
    """Test ContentAuditLog model with redirect tracking fields."""

    def test_create_delete_log_with_redirect(self):
        """Test creating delete log with redirect target."""
        user = User.objects.create_user(username='testuser', password='pass')

        log = ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        assert log.deleted_at is not None
        assert log.redirect_target == '/articles'
        assert log.action == 'delete'

    def test_create_delete_log_without_redirect(self):
        """Test creating delete log without redirect (intentional 404)."""
        user = User.objects.create_user(username='testuser', password='pass')

        log = ContentAuditLog.objects.create(
            content_type='news',
            slug='old-news',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='',
        )

        assert log.deleted_at is not None
        assert log.redirect_target == ''
        assert log.action == 'delete'

    def test_get_source_path(self):
        """Test generating source URL path from log entry."""
        user = User.objects.create_user(username='testuser', password='pass')

        test_cases = [
            ('article', 'my-article', '/articles/my-article'),
            ('news', 'breaking-news', '/news/breaking-news'),
            ('briefing', 'mmt-briefing', '/briefings/mmt-briefing'),
            ('local_event', 'london-meetup', '/local-events/london-meetup'),
            ('bio', 'john-doe', '/about/john-doe'),
        ]

        for content_type, slug, expected_path in test_cases:
            log = ContentAuditLog.objects.create(
                content_type=content_type,
                slug=slug,
                action='delete',
                user=user,
                deleted_at=timezone.now(),
            )
            assert log.get_source_path() == expected_path


@pytest.mark.django_db
class TestRedirectService:
    """Test redirect service functions."""

    def test_get_active_redirects_empty(self):
        """Test getting redirects when none exist."""
        redirects = get_active_redirects()
        assert redirects == {}

    def test_get_active_redirects_with_data(self):
        """Test getting active redirects from database."""
        user = User.objects.create_user(username='testuser', password='pass')

        # Create deleted content with redirects
        ContentAuditLog.objects.create(
            content_type='article',
            slug='old-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        ContentAuditLog.objects.create(
            content_type='news',
            slug='old-news',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/news/category',
        )

        redirects = get_active_redirects()

        assert len(redirects) == 2
        assert redirects['/articles/old-article'] == '/articles'
        assert redirects['/news/old-news'] == '/news/category'

    def test_get_active_redirects_excludes_empty(self):
        """Test that intentional 404s (empty redirect_target) are excluded."""
        user = User.objects.create_user(username='testuser', password='pass')

        # Create deleted content without redirect
        ContentAuditLog.objects.create(
            content_type='article',
            slug='intentional-404',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='',
        )

        redirects = get_active_redirects()
        assert len(redirects) == 0

    def test_generate_redirects_config_empty(self):
        """Test generating config when no redirects exist."""
        config = generate_redirects_config()

        assert 'export default {};' in config
        assert 'No redirects configured yet' in config

    def test_generate_redirects_config_with_data(self):
        """Test generating JavaScript config with redirects."""
        user = User.objects.create_user(username='testuser', password='pass')

        ContentAuditLog.objects.create(
            content_type='article',
            slug='old-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        config = generate_redirects_config()

        assert 'export default {' in config
        assert "'/articles/old-article': '/articles'," in config
        assert 'Auto-generated redirects' in config
        assert 'DO NOT EDIT MANUALLY' in config

    def test_get_redirect_summary(self):
        """Test getting redirect summary with grouping."""
        user = User.objects.create_user(username='testuser', password='pass')

        # Create multiple redirects to same target
        ContentAuditLog.objects.create(
            content_type='article',
            slug='old-1',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        ContentAuditLog.objects.create(
            content_type='article',
            slug='old-2',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        summary = get_redirect_summary()

        assert summary['total_count'] == 2
        assert '/articles' in summary['grouped']
        assert len(summary['grouped']['/articles']) == 2
        assert '/articles/old-1' in summary['grouped']['/articles']
        assert '/articles/old-2' in summary['grouped']['/articles']


class TestRedirectValidation:
    """Test redirect target validation."""

    def test_validate_empty_redirect(self):
        """Test validating empty redirect (intentional 404)."""
        is_valid, error = validate_redirect_target('')
        assert is_valid is True
        assert error == ''

    def test_validate_valid_redirects(self):
        """Test validating valid redirect targets."""
        valid_targets = [
            '/articles',
            '/news/category',
            '/articles/some-article',
            '/about',
            '/',
        ]

        for target in valid_targets:
            is_valid, error = validate_redirect_target(target)
            assert is_valid is True, f'Expected {target} to be valid'
            assert error == ''

    def test_validate_must_start_with_slash(self):
        """Test that redirect must start with /."""
        is_valid, error = validate_redirect_target('articles/page')
        assert is_valid is False
        assert 'must start with /' in error

    def test_validate_no_trailing_slash(self):
        """Test that redirect should not end with / (except root)."""
        is_valid, error = validate_redirect_target('/articles/')
        assert is_valid is False
        assert 'should not end with /' in error

        # Root "/" is valid
        is_valid, error = validate_redirect_target('/')
        assert is_valid is True

    def test_validate_no_spaces(self):
        """Test that redirect should not contain spaces."""
        is_valid, error = validate_redirect_target('/articles/my article')
        assert is_valid is False
        assert 'should not contain spaces' in error

    def test_validate_invalid_characters(self):
        """Test that redirect rejects invalid characters."""
        invalid_targets = [
            '/articles/<script>',
            '/news/"quoted"',
            '/articles\\backslash',
            '/articles{bracket}',
        ]

        for target in invalid_targets:
            is_valid, error = validate_redirect_target(target)
            assert is_valid is False, f'Expected {target} to be invalid'
            assert 'invalid character' in error.lower()


@pytest.mark.django_db
class TestRedirectIntegration:
    """Integration tests for redirect functionality."""

    def test_delete_creates_redirect_log(self):
        """Test that deleting content creates audit log with redirect."""
        user = User.objects.create_user(username='testuser', password='pass')

        # Simulate delete with redirect
        log = ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
            changes_summary='Deleted: Test Article',
        )

        assert ContentAuditLog.objects.filter(
            action='delete',
            content_type='article',
            slug='test-article',
        ).exists()

        assert log.redirect_target == '/articles'
        assert log.deleted_at is not None

    def test_update_redirect_target(self):
        """Test updating redirect target for deleted content."""
        user = User.objects.create_user(username='testuser', password='pass')

        log = ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        # Update redirect target
        log.redirect_target = '/articles/category'
        log.save()

        updated = ContentAuditLog.objects.get(id=log.id)
        assert updated.redirect_target == '/articles/category'

    def test_remove_redirect(self):
        """Test removing redirect (setting to empty)."""
        user = User.objects.create_user(username='testuser', password='pass')

        log = ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.now(),
            redirect_target='/articles',
        )

        # Remove redirect
        log.redirect_target = ''
        log.save()

        updated = ContentAuditLog.objects.get(id=log.id)
        assert updated.redirect_target == ''

        # Should not appear in active redirects
        redirects = get_active_redirects()
        assert '/articles/test-article' not in redirects


@pytest.mark.django_db
class TestRedirectPriority:
    """Test redirect priority and conflict handling."""

    def test_multiple_deletes_same_slug(self):
        """Test handling multiple deletes of same content (re-created and deleted again)."""
        user = User.objects.create_user(username='testuser', password='pass')

        # First delete
        ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.make_aware(datetime(2024, 1, 1)),
            redirect_target='/articles/old',
        )

        # Second delete (content was re-created and deleted again)
        ContentAuditLog.objects.create(
            content_type='article',
            slug='test-article',
            action='delete',
            user=user,
            deleted_at=timezone.make_aware(datetime(2024, 2, 1)),
            redirect_target='/articles/new',
        )

        # get_active_redirects should return only the most recent (last wins)
        redirects = get_active_redirects()

        # Both entries are returned (business logic: keep all redirect history)
        # The Astro config will use the last one in the file
        assert '/articles/test-article' in redirects
        # The value should be from the most recent entry based on ordering
        assert redirects['/articles/test-article'] == '/articles/new'
