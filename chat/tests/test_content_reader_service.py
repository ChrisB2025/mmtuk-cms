"""Unit tests for chat/services/content_reader_service.py."""

import pytest
from datetime import date

from chat.services.content_reader_service import (
    list_content, read_content, search_content,
    get_content_stats, check_slug_exists,
)
from content.models import Article, Briefing


pytestmark = pytest.mark.django_db


class TestListContent:

    def test_list_all(self, sample_article, sample_briefing):
        results = list_content()
        slugs = {r['slug'] for r in results}
        assert 'test-article' in slugs
        assert 'test-briefing' in slugs

    def test_list_by_type(self, sample_article, sample_briefing):
        results = list_content('article')
        assert all(r['content_type'] == 'article' for r in results)
        assert len(results) == 1

    def test_list_empty(self):
        results = list_content('article')
        assert results == []


class TestReadContent:

    def test_read_existing(self, sample_article):
        result = read_content('article', 'test-article')
        assert result is not None
        assert result['body'] == 'Test body.'
        assert result['frontmatter']['title'] == 'Test Article'

    def test_read_nonexistent(self):
        result = read_content('article', 'nonexistent')
        assert result is None

    def test_read_returns_camelcase_keys(self, sample_article):
        result = read_content('article', 'test-article')
        fm = result['frontmatter']
        assert 'pubDate' in fm  # camelCase, not pub_date
        assert 'pub_date' not in fm


class TestSearchContent:

    def test_search_by_title(self, sample_article):
        results = search_content('Test Article')
        assert len(results) >= 1
        assert any(r['slug'] == 'test-article' for r in results)

    def test_search_by_body(self, sample_article):
        results = search_content('Test body')
        assert any(r['slug'] == 'test-article' for r in results)

    def test_search_by_author(self, sample_article):
        results = search_content('MMTUK')
        assert any(r['slug'] == 'test-article' for r in results)

    def test_search_empty_query(self):
        results = search_content('')
        assert results == []

    def test_search_whitespace_query(self):
        results = search_content('   ')
        assert results == []

    def test_search_filtered_by_type(self, sample_article, sample_briefing):
        results = search_content('Test', content_type='article')
        assert all(r['content_type'] == 'article' for r in results)


class TestContentStats:

    def test_stats_with_content(self, sample_article, sample_briefing):
        stats = get_content_stats()
        assert stats['total'] >= 2
        assert 'article' in stats['by_type']
        assert stats['by_type']['article']['count'] == 1

    def test_stats_draft_count(self, sample_article):
        Article.objects.create(
            title='Draft', slug='draft-article', category='Article',
            author='X', pub_date=date(2026, 1, 1), status='draft',
        )
        stats = get_content_stats()
        assert stats['by_type']['article']['draft_count'] == 1

    def test_stats_briefing_dual_flag(self, sample_briefing):
        # Create a briefing with draft=True but status='published'
        Briefing.objects.create(
            title='Draft Briefing', slug='draft-briefing', author='X',
            pub_date=date(2026, 1, 1), draft=True, status='published',
        )
        stats = get_content_stats()
        # Should count both status='draft' AND draft=True with status='published'
        assert stats['by_type']['briefing']['draft_count'] >= 1


class TestCheckSlugExists:

    def test_exists(self, sample_article):
        assert check_slug_exists('article', 'test-article') is True

    def test_not_exists(self):
        assert check_slug_exists('article', 'nonexistent') is False

    def test_invalid_type(self):
        assert check_slug_exists('invalid', 'x') is False
