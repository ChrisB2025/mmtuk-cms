"""Unit tests for chat/services/anthropic_service.py helper functions."""

import pytest
from datetime import date

from chat.services.anthropic_service import (
    extract_action_block, strip_action_block, build_system_prompt,
)


class TestExtractActionBlock:

    def test_extract_create_action(self):
        text = '''Here's the article.

```json
{
  "action": "create",
  "content_type": "article",
  "frontmatter": {"title": "Test"}
}
```

Let me know!'''
        result = extract_action_block(text)
        assert result is not None
        assert result['action'] == 'create'
        assert result['content_type'] == 'article'

    def test_extract_edit_action(self):
        text = '''```json
{"action": "edit", "content_type": "article", "slug": "test"}
```'''
        result = extract_action_block(text)
        assert result['action'] == 'edit'

    def test_no_block(self):
        result = extract_action_block('Just a normal response with no JSON.')
        assert result is None

    def test_invalid_json(self):
        text = '```json\n{not valid json}\n```'
        result = extract_action_block(text)
        assert result is None

    def test_missing_action_key(self):
        text = '```json\n{"content_type": "article"}\n```'
        result = extract_action_block(text)
        assert result is None


class TestStripActionBlock:

    def test_strip_removes_json_block(self):
        text = '''Here's the article.

```json
{"action": "create", "content_type": "article"}
```

Let me know!'''
        result = strip_action_block(text)
        assert '```json' not in result
        assert '"action"' not in result

    def test_strip_preserves_surrounding_text(self):
        text = '''Before.

```json
{"action": "create"}
```

After.'''
        result = strip_action_block(text)
        assert 'Before.' in result
        assert 'After.' in result

    def test_strip_no_block(self):
        text = 'Just text, no JSON.'
        assert strip_action_block(text) == text


@pytest.mark.django_db
class TestBuildSystemPrompt:

    def test_includes_user_context(self, admin_user):
        prompt = build_system_prompt(admin_user.profile)
        assert 'admin' in prompt.lower() or 'Admin' in prompt

    def test_includes_date(self, admin_user):
        prompt = build_system_prompt(admin_user.profile)
        today_str = date.today().strftime('%d %B %Y')
        assert today_str in prompt

    def test_includes_schema_details(self, admin_user):
        prompt = build_system_prompt(admin_user.profile)
        # Should mention at least some content types
        assert 'article' in prompt.lower() or 'Article' in prompt
        assert 'briefing' in prompt.lower() or 'Briefing' in prompt
