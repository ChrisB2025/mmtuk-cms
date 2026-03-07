"""Integration tests for content action handlers (create/edit/delete) through the view layer."""

import json
import pytest
from unittest.mock import patch

from django.urls import reverse

from chat.models import Conversation, ContentDraft, ContentAuditLog
from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)


pytestmark = pytest.mark.django_db


def _send(client, conv_id, message):
    url = reverse('send_message', args=[conv_id])
    return client.post(
        url,
        data=json.dumps({'message': message}),
        content_type='application/json',
    )


def _mock_create_response(content_type, frontmatter, body='Body text.'):
    """Build a mock Claude response with a create action block."""
    fm_json = json.dumps(frontmatter)
    return f'''Creating content.

```json
{{
  "action": "create",
  "content_type": "{content_type}",
  "frontmatter": {fm_json},
  "body": "{body}"
}}
```

Done!'''


def _mock_edit_response(content_type, slug, frontmatter, body=None):
    """Build a mock Claude response with an edit action block."""
    block = {
        'action': 'edit',
        'content_type': content_type,
        'slug': slug,
        'frontmatter': frontmatter,
    }
    if body is not None:
        block['body'] = body
    return f'''Editing.\n\n```json\n{json.dumps(block)}\n```\n\nDone!'''


def _mock_delete_response(content_type, slug):
    block = json.dumps({'action': 'delete', 'content_type': content_type, 'slug': slug})
    return f'Deleting.\n\n```json\n{block}\n```\n\nDeleted!'


class TestCreateActions:

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_admin_creates_article(self, mock_claude, mock_img, admin_client, conversation):
        mock_claude.return_value = _mock_create_response('article', {
            'title': 'Chat Article', 'slug': 'chat-article',
            'category': 'Article', 'author': 'MMTUK', 'pubDate': '2026-01-15',
        })
        resp = _send(admin_client, conversation.id, 'create article')
        assert resp.status_code == 200
        assert Article.objects.filter(slug='chat-article').exists()

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_admin_creates_briefing(self, mock_claude, mock_img, admin_client, conversation):
        mock_claude.return_value = _mock_create_response('briefing', {
            'title': 'Chat Briefing', 'slug': 'chat-briefing',
            'author': 'MMTUK', 'pubDate': '2026-01-10',
        })
        _send(admin_client, conversation.id, 'create briefing')
        assert Briefing.objects.filter(slug='chat-briefing').exists()

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_admin_creates_news(self, mock_claude, mock_img, admin_client, conversation):
        mock_claude.return_value = _mock_create_response('news', {
            'title': 'Chat News', 'slug': 'chat-news',
            'date': '2026-02-01', 'category': 'Announcement',
        })
        _send(admin_client, conversation.id, 'create news')
        assert News.objects.filter(slug='chat-news').exists()

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_admin_creates_bio(self, mock_claude, mock_img, admin_client, conversation):
        mock_claude.return_value = _mock_create_response('bio', {
            'name': 'Test Person', 'slug': 'test-person', 'role': 'Researcher',
        })
        _send(admin_client, conversation.id, 'create bio')
        assert Bio.objects.filter(slug='test-person').exists()

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_admin_creates_local_event(
        self, mock_claude, mock_img, admin_client, conversation, local_group_brighton,
    ):
        mock_claude.return_value = _mock_create_response('local_event', {
            'title': 'Chat Event', 'slug': 'chat-event',
            'localGroup': 'brighton', 'date': '2026-03-01',
            'tag': 'Meetup', 'location': 'Library', 'description': 'A meetup.',
        })
        _send(admin_client, conversation.id, 'create event')
        event = LocalEvent.objects.get(slug='chat-event')
        assert event.local_group.slug == 'brighton'

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_duplicate_slug_rejected(
        self, mock_claude, mock_img, admin_client, conversation, sample_article,
    ):
        mock_claude.return_value = _mock_create_response('article', {
            'title': 'Duplicate', 'slug': 'test-article',
            'category': 'Article', 'author': 'X', 'pubDate': '2026-01-01',
        })
        resp = _send(admin_client, conversation.id, 'create article')
        data = resp.json()
        # Should not crash — error handled gracefully
        assert resp.status_code == 200

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_contributor_create_goes_to_draft(
        self, mock_claude, mock_img, contributor_client, contributor_user,
    ):
        conv = Conversation.objects.create(user=contributor_user)
        mock_claude.return_value = _mock_create_response('article', {
            'title': 'Draft Article', 'slug': 'draft-article',
            'category': 'Article', 'author': 'MMTUK', 'pubDate': '2026-01-15',
        })
        resp = _send(contributor_client, conv.id, 'create article')
        assert resp.status_code == 200
        # Should NOT be published directly
        assert not Article.objects.filter(slug='draft-article').exists()
        # Should have a pending draft
        assert ContentDraft.objects.filter(slug='draft-article', status='pending').exists()


class TestEditActions:

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_edit_updates_content(
        self, mock_claude, mock_img, admin_client, conversation, sample_article,
    ):
        mock_claude.return_value = _mock_edit_response(
            'article', 'test-article', {'title': 'Updated Title'},
        )
        resp = _send(admin_client, conversation.id, 'edit article')
        assert resp.status_code == 200
        sample_article.refresh_from_db()
        assert sample_article.title == 'Updated Title'

    @patch('chat.views.call_claude')
    def test_edit_nonexistent_slug(self, mock_claude, admin_client, conversation):
        mock_claude.return_value = _mock_edit_response(
            'article', 'nonexistent', {'title': 'X'},
        )
        resp = _send(admin_client, conversation.id, 'edit article')
        assert resp.status_code == 200  # error handled, not 500


class TestDeleteActions:

    @patch('chat.views.call_claude')
    def test_delete_removes_content(self, mock_claude, admin_client, conversation, sample_article):
        mock_claude.return_value = _mock_delete_response('article', 'test-article')
        resp = _send(admin_client, conversation.id, 'delete article')
        assert resp.status_code == 200
        assert not Article.objects.filter(slug='test-article').exists()

    @patch('chat.views.call_claude')
    def test_delete_nonexistent_slug(self, mock_claude, admin_client, conversation):
        mock_claude.return_value = _mock_delete_response('article', 'nonexistent')
        resp = _send(admin_client, conversation.id, 'delete article')
        assert resp.status_code == 200  # error handled


class TestListReadActions:

    @patch('chat.views.call_claude')
    def test_list_action(self, mock_claude, admin_client, conversation, sample_article):
        block = json.dumps({'action': 'list', 'content_type': 'article'})
        mock_claude.return_value = f'Listing.\n\n```json\n{block}\n```'
        resp = _send(admin_client, conversation.id, 'list articles')
        assert resp.status_code == 200

    @patch('chat.views.call_claude')
    def test_read_action(self, mock_claude, admin_client, conversation, sample_article):
        block = json.dumps({'action': 'read', 'content_type': 'article', 'slug': 'test-article'})
        mock_claude.return_value = f'Reading.\n\n```json\n{block}\n```'
        resp = _send(admin_client, conversation.id, 'read article')
        assert resp.status_code == 200
