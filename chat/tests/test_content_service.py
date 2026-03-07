"""Unit tests for chat/services/content_service.py."""

import pytest
from datetime import date

from chat.services.content_service import (
    create_content, update_content, delete_content,
    get_image_save_path, estimate_read_time,
)
from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)


pytestmark = pytest.mark.django_db


class TestCreateContent:

    def test_create_article(self, article_frontmatter):
        instance, errors = create_content('article', article_frontmatter, body='Body text.')
        assert errors == []
        assert instance is not None
        assert Article.objects.filter(slug='new-article').exists()
        assert instance.body == 'Body text.'
        assert instance.status == 'published'

    def test_create_briefing(self, briefing_frontmatter):
        instance, errors = create_content('briefing', briefing_frontmatter)
        assert errors == []
        assert Briefing.objects.filter(slug='new-briefing').exists()

    def test_create_news(self, news_frontmatter):
        instance, errors = create_content('news', news_frontmatter)
        assert errors == []
        assert News.objects.filter(slug='new-news').exists()

    def test_create_bio(self, bio_frontmatter):
        instance, errors = create_content('bio', bio_frontmatter)
        assert errors == []
        assert Bio.objects.filter(slug='john-smith').exists()

    def test_create_ecosystem(self, ecosystem_frontmatter):
        instance, errors = create_content('ecosystem', ecosystem_frontmatter)
        assert errors == []
        entry = EcosystemEntry.objects.get(slug='new-org')
        assert entry.activity_status == 'Active'

    def test_create_local_group(self, local_group_frontmatter):
        instance, errors = create_content('local_group', local_group_frontmatter)
        assert errors == []
        assert LocalGroup.objects.filter(slug='oxford').exists()

    def test_create_local_event(self, local_event_frontmatter):
        instance, errors = create_content('local_event', local_event_frontmatter)
        assert errors == []
        event = LocalEvent.objects.get(slug='new-event')
        assert event.local_group.slug == 'brighton'

    def test_create_local_news(self, local_news_frontmatter):
        instance, errors = create_content('local_news', local_news_frontmatter)
        assert errors == []
        news = LocalNews.objects.get(slug='new-local-news')
        assert news.heading == 'New Local News'
        assert news.local_group.slug == 'brighton'

    def test_create_with_draft_status(self, article_frontmatter):
        instance, errors = create_content('article', article_frontmatter, status='draft')
        assert errors == []
        assert instance.status == 'draft'

    def test_create_invalid_type(self):
        instance, errors = create_content('invalid', {'title': 'x'})
        assert instance is None
        assert len(errors) == 1
        assert 'Unknown content type' in errors[0]

    def test_create_missing_required_field(self):
        instance, errors = create_content('article', {'title': 'No Slug'})
        assert instance is None
        assert len(errors) > 0

    def test_create_duplicate_slug(self, sample_article, article_frontmatter):
        article_frontmatter['slug'] = 'test-article'  # already exists
        instance, errors = create_content('article', article_frontmatter)
        assert instance is None
        assert len(errors) > 0

    def test_create_article_auto_layout_core_ideas(self, article_frontmatter):
        article_frontmatter['category'] = 'Core Ideas'
        instance, errors = create_content('article', article_frontmatter)
        assert errors == []
        assert instance.layout == 'simplified'

    def test_create_article_auto_layout_rebuttal(self, article_frontmatter):
        article_frontmatter['category'] = 'But what about...?'
        instance, errors = create_content('article', article_frontmatter)
        assert errors == []
        assert instance.layout == 'rebuttal'

    def test_create_article_explicit_layout_preserved(self, article_frontmatter):
        article_frontmatter['category'] = 'Core Ideas'
        article_frontmatter['layout'] = 'default'
        instance, errors = create_content('article', article_frontmatter)
        assert errors == []
        assert instance.layout == 'default'

    def test_create_invalid_fk(self):
        fm = {
            'title': 'Event', 'slug': 'event', 'localGroup': 'nonexistent',
            'date': '2026-01-01', 'tag': 'X', 'location': 'Y',
            'description': 'Z',
        }
        instance, errors = create_content('local_event', fm)
        assert instance is None
        assert any('no LocalGroup' in e for e in errors)


class TestUpdateContent:

    def test_update_title(self, sample_article):
        instance, errors = update_content('article', 'test-article', {'title': 'Updated'})
        assert errors == []
        assert instance.title == 'Updated'
        sample_article.refresh_from_db()
        assert sample_article.title == 'Updated'

    def test_update_body_only(self, sample_article):
        instance, errors = update_content('article', 'test-article', body='New body.')
        assert errors == []
        assert instance.body == 'New body.'

    def test_update_not_found(self):
        instance, errors = update_content('article', 'nonexistent', {'title': 'X'})
        assert instance is None
        assert 'not found' in errors[0]

    def test_update_invalid_type(self):
        instance, errors = update_content('invalid', 'x', {'title': 'X'})
        assert instance is None
        assert 'Unknown content type' in errors[0]

    def test_update_article_auto_layout_on_category_change(self, sample_article):
        instance, errors = update_content('article', 'test-article', {'category': 'Core Ideas'})
        assert errors == []
        assert instance.layout == 'simplified'

    def test_update_fk_field(self, sample_local_event, local_group_brighton):
        # Create a second group
        oxford = LocalGroup.objects.create(
            name='Oxford', slug='oxford', title='MMTUK Oxford', tagline='Oxford group',
        )
        instance, errors = update_content(
            'local_event', 'brighton-meetup', {'localGroup': 'oxford'}
        )
        assert errors == []
        assert instance.local_group == oxford


class TestDeleteContent:

    def test_delete_success(self, sample_article):
        success, error = delete_content('article', 'test-article')
        assert success is True
        assert error is None
        assert not Article.objects.filter(slug='test-article').exists()

    def test_delete_not_found(self):
        success, error = delete_content('article', 'nonexistent')
        assert success is False
        assert 'not found' in error

    def test_delete_invalid_type(self):
        success, error = delete_content('invalid', 'x')
        assert success is False
        assert 'Unknown content type' in error

    def test_delete_fk_protection(self, sample_local_event):
        """Deleting a LocalGroup with linked events should fail (PROTECT)."""
        success, error = delete_content('local_group', 'brighton')
        assert success is False


class TestGetImageSavePath:

    def test_bio_path(self):
        abs_path, web_path = get_image_save_path('bio', 'jane-doe')
        assert abs_path.name == 'jane-doe.webp'
        assert 'bios' in abs_path.parts
        assert web_path == '/images/bios/jane-doe.webp'

    def test_briefing_path(self):
        abs_path, web_path = get_image_save_path('briefing', 'my-briefing')
        assert abs_path.name == 'my-briefing-thumbnail.webp'
        assert 'briefings' in abs_path.parts
        assert web_path == '/images/briefings/my-briefing-thumbnail.webp'

    def test_article_path(self):
        abs_path, web_path = get_image_save_path('article', 'my-article')
        assert abs_path.name == 'my-article.webp'
        assert web_path == '/images/my-article.webp'

    def test_custom_extension(self):
        _, web_path = get_image_save_path('article', 'test', extension='png')
        assert web_path == '/images/test.png'


class TestEstimateReadTime:

    def test_short_text(self):
        assert estimate_read_time('hello world') == 1  # minimum 1

    def test_medium_text(self):
        text = ' '.join(['word'] * 600)
        assert estimate_read_time(text) == 3  # 600/200 = 3

    def test_empty_text(self):
        assert estimate_read_time('') == 1  # minimum 1
