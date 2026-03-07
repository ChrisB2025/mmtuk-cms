"""Integration tests for the content browser, quick-edit, delete, and toggle-featured views."""

import json
import pytest
from django.urls import reverse

from content.models import Article


pytestmark = pytest.mark.django_db


class TestContentBrowser:

    def test_lists_content(self, admin_client, sample_article, sample_briefing):
        resp = admin_client.get(reverse('content_browser'))
        assert resp.status_code == 200
        slugs = {item['slug'] for item in resp.context['items']}
        assert 'test-article' in slugs
        assert 'test-briefing' in slugs

    def test_type_filter(self, admin_client, sample_article, sample_briefing):
        resp = admin_client.get(reverse('content_browser') + '?type=article')
        assert resp.status_code == 200
        assert all(item['content_type'] == 'article' for item in resp.context['items'])

    def test_search(self, admin_client, sample_article, sample_briefing):
        resp = admin_client.get(reverse('content_browser') + '?q=Test+Article')
        assert resp.status_code == 200
        slugs = {item['slug'] for item in resp.context['items']}
        assert 'test-article' in slugs


class TestQuickEdit:

    def test_updates_field(self, admin_client, sample_article):
        url = reverse('quick_edit', args=['article', 'test-article'])
        resp = admin_client.post(url, data={'fm_title': 'Quick Edited'})
        # Should redirect to content detail
        assert resp.status_code == 302
        sample_article.refresh_from_db()
        assert sample_article.title == 'Quick Edited'

    def test_contributor_permission_denied(self, contributor_client, sample_article):
        url = reverse('quick_edit', args=['article', 'test-article'])
        resp = contributor_client.post(url, data={'fm_title': 'Hacked'})
        assert resp.status_code == 403
        sample_article.refresh_from_db()
        assert sample_article.title == 'Test Article'  # unchanged


class TestDeleteContentView:

    def test_deletes_content(self, admin_client, sample_article):
        url = reverse('delete_content', args=['article', 'test-article'])
        resp = admin_client.post(url)
        assert resp.status_code == 302  # redirect to browser
        assert not Article.objects.filter(slug='test-article').exists()

    def test_contributor_permission_denied(self, contributor_client, sample_article):
        url = reverse('delete_content', args=['article', 'test-article'])
        resp = contributor_client.post(url)
        assert resp.status_code == 403
        assert Article.objects.filter(slug='test-article').exists()


class TestToggleFeatured:

    def test_toggles_featured(self, admin_client, sample_article):
        assert sample_article.featured is False
        url = reverse('toggle_featured', args=['article', 'test-article'])
        resp = admin_client.post(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data['featured'] is True
        sample_article.refresh_from_db()
        assert sample_article.featured is True

        # Toggle back
        resp = admin_client.post(url)
        data = resp.json()
        assert data['featured'] is False

    def test_contributor_permission_denied(self, contributor_client, sample_article):
        url = reverse('toggle_featured', args=['article', 'test-article'])
        resp = contributor_client.post(url)
        assert resp.status_code == 403
