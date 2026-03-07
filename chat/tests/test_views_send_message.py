"""Integration tests for the send_message view."""

import json
import pytest
from unittest.mock import patch

from django.urls import reverse

from chat.models import Message, Conversation
from content.models import Article


pytestmark = pytest.mark.django_db


def _send(client, conv_id, message):
    """Helper to POST a message to send_message view."""
    url = reverse('send_message', args=[conv_id])
    return client.post(
        url,
        data=json.dumps({'message': message}),
        content_type='application/json',
    )


class TestSendMessageBasic:

    def test_requires_login(self, conversation):
        from django.test import Client
        client = Client()  # not logged in
        resp = _send(client, conversation.id, 'hello')
        assert resp.status_code == 302  # redirect to login

    def test_empty_message_rejected(self, admin_client, conversation):
        url = reverse('send_message', args=[conversation.id])
        resp = admin_client.post(
            url,
            data=json.dumps({'message': ''}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_json_rejected(self, admin_client, conversation):
        url = reverse('send_message', args=[conversation.id])
        resp = admin_client.post(url, data='not json', content_type='application/json')
        assert resp.status_code == 400

    @patch('chat.views.call_claude', return_value='Hello! How can I help?')
    def test_user_message_saved_to_db(self, mock_claude, admin_client, conversation):
        _send(admin_client, conversation.id, 'Create an article')
        user_msgs = Message.objects.filter(
            conversation=conversation, role='user',
        )
        assert user_msgs.count() == 1
        assert user_msgs.first().content == 'Create an article'

    @patch('chat.views.call_claude', return_value='Hello!')
    def test_assistant_response_saved(self, mock_claude, admin_client, conversation):
        _send(admin_client, conversation.id, 'Hello')
        asst_msgs = Message.objects.filter(
            conversation=conversation, role='assistant',
        )
        assert asst_msgs.count() == 1

    @patch('chat.views.call_claude', return_value='Hello!')
    def test_conversation_title_set(self, mock_claude, admin_client, conversation):
        _send(admin_client, conversation.id, 'Create a briefing about MMT')
        conversation.refresh_from_db()
        assert conversation.title == 'Create a briefing about MMT'


class TestSendMessageWithActions:

    MOCK_CREATE_RESPONSE = '''Here's the article.

```json
{
  "action": "create",
  "content_type": "article",
  "frontmatter": {
    "title": "Test Article",
    "slug": "test-via-chat",
    "category": "Article",
    "author": "MMTUK",
    "pubDate": "2026-01-15"
  },
  "body": "Article body."
}
```

Created!'''

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_create_action_publishes_for_admin(
        self, mock_claude, mock_img, admin_client, conversation
    ):
        mock_claude.return_value = self.MOCK_CREATE_RESPONSE
        resp = _send(admin_client, conversation.id, 'Create an article')
        data = resp.json()
        assert resp.status_code == 200
        assert Article.objects.filter(slug='test-via-chat').exists()
        assert data['action_taken'] is not None

    @patch('chat.views.process_image', return_value=(None, None))
    @patch('chat.views.call_claude')
    def test_create_action_drafts_for_contributor(
        self, mock_claude, mock_img, contributor_client, contributor_user
    ):
        conv = Conversation.objects.create(user=contributor_user)
        mock_claude.return_value = self.MOCK_CREATE_RESPONSE
        resp = _send(contributor_client, conv.id, 'Create an article')
        data = resp.json()
        assert resp.status_code == 200
        # Contributor can't publish directly — should go to draft
        assert not Article.objects.filter(slug='test-via-chat').exists()
        if data['action_taken']:
            assert data['action_taken']['type'] in ('draft_pending', 'content_created')

    @patch('chat.views.call_claude', return_value='No action here, just chat.')
    def test_conversational_response(self, mock_claude, admin_client, conversation):
        resp = _send(admin_client, conversation.id, 'Tell me about MMT')
        data = resp.json()
        assert resp.status_code == 200
        assert data['action_taken'] is None
        assert 'No action here' in data['response']

    @patch('chat.views.call_claude')
    def test_action_block_stripped_from_display(self, mock_claude, admin_client, conversation):
        mock_claude.return_value = '''Text before.

```json
{"action": "list", "content_type": "article"}
```

Text after.'''
        resp = _send(admin_client, conversation.id, 'List articles')
        data = resp.json()
        assert '```json' not in data['response']
