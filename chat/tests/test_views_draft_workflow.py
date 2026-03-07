"""Integration tests for the draft approval/rejection workflow."""

import pytest
from django.urls import reverse

from chat.models import ContentDraft, Conversation
from content.models import Article


pytestmark = pytest.mark.django_db


def _create_pending_draft(user, content_type='article', slug='draft-slug', frontmatter=None):
    """Helper to create a pending ContentDraft."""
    fm = frontmatter or {
        'title': 'Draft Title',
        'slug': slug,
        'category': 'Article',
        'author': 'MMTUK',
        'pubDate': '2026-01-20',
    }
    return ContentDraft.objects.create(
        created_by=user,
        content_type=content_type,
        title=fm.get('title') or fm.get('heading') or fm.get('name', 'Draft'),
        slug=slug,
        frontmatter_json=fm,
        body_markdown='Draft body text.',
        status='pending',
    )


class TestPendingList:

    def test_admin_sees_all_pending(self, admin_client, admin_user, contributor_user):
        _create_pending_draft(contributor_user, slug='draft-1')
        _create_pending_draft(contributor_user, slug='draft-2')
        resp = admin_client.get(reverse('pending_list'))
        assert resp.status_code == 200
        assert len(resp.context['drafts']) == 2

    def test_group_lead_forbidden(self, group_lead_client):
        """Group leads can't access pending list — can_approve() with no args returns False."""
        resp = group_lead_client.get(reverse('pending_list'))
        assert resp.status_code == 403

    def test_contributor_forbidden(self, contributor_client):
        resp = contributor_client.get(reverse('pending_list'))
        assert resp.status_code == 403


class TestApproveDraft:

    def test_approve_creates_content(self, admin_client, admin_user, contributor_user):
        draft = _create_pending_draft(contributor_user, slug='approve-me')
        resp = admin_client.post(reverse('approve_draft', args=[draft.id]))
        # Should redirect to pending list
        assert resp.status_code == 302
        # Article should now exist in DB
        assert Article.objects.filter(slug='approve-me').exists()
        # Draft should be marked approved
        draft.refresh_from_db()
        assert draft.status == 'approved'
        assert draft.reviewer == admin_user

    def test_approve_updates_existing_slug(
        self, admin_client, admin_user, contributor_user, sample_article,
    ):
        """If the draft slug matches an existing article, approve should update it."""
        draft = _create_pending_draft(
            contributor_user, slug='test-article',
            frontmatter={
                'title': 'Updated Title',
                'slug': 'test-article',
                'category': 'Article',
                'author': 'MMTUK',
                'pubDate': '2026-01-15',
            },
        )
        resp = admin_client.post(reverse('approve_draft', args=[draft.id]))
        assert resp.status_code == 302
        sample_article.refresh_from_db()
        assert sample_article.title == 'Updated Title'

    def test_contributor_cannot_approve(self, contributor_client, contributor_user):
        draft = _create_pending_draft(contributor_user, slug='no-approve')
        resp = contributor_client.post(reverse('approve_draft', args=[draft.id]))
        assert resp.status_code == 403


class TestRejectDraft:

    def test_reject_sets_status_and_feedback(
        self, admin_client, admin_user, contributor_user,
    ):
        draft = _create_pending_draft(contributor_user, slug='reject-me')
        resp = admin_client.post(
            reverse('reject_draft', args=[draft.id]),
            data={'feedback': 'Needs more detail.'},
        )
        assert resp.status_code == 302
        draft.refresh_from_db()
        assert draft.status == 'rejected'
        assert draft.review_feedback == 'Needs more detail.'
        assert draft.reviewer == admin_user

    def test_contributor_cannot_reject(self, contributor_client, contributor_user):
        draft = _create_pending_draft(contributor_user, slug='no-reject')
        resp = contributor_client.post(reverse('reject_draft', args=[draft.id]))
        assert resp.status_code == 403
