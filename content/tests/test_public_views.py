"""Smoke tests for every public-facing URL.

Each test hits the URL and checks for 200 (or expected redirect).
This catches 500 errors, missing templates, broken page data, and
template syntax errors before cutover.
"""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


# --- Static pages (no DB content required) ---

class TestStaticPages:
    """Pages that only depend on JSON page data, not DB content."""

    @pytest.mark.parametrize('url', [
        '/',
        '/research/',
        '/education/',
        '/community/',
        '/about-us/',
        '/donate/',
        '/join/',
        '/founders/',
        '/founders/launch-event/',
        '/privacy-policy/',
        '/terms-of-engagement/',
        '/cookie-preferences/',
        '/articles/',
        '/research/briefings/',
        '/research/job-guarantee/',
    ])
    def test_page_returns_200(self, client, url):
        response = client.get(url)
        assert response.status_code == 200, f'{url} returned {response.status_code}'

    def test_robots_txt(self, client):
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/plain'
        content = response.content.decode()
        assert 'User-agent: *' in content
        assert 'Disallow: /cms/' in content
        assert 'Disallow: /admin/' in content


# --- Detail pages (require DB content) ---

class TestArticleDetail:
    def test_returns_200(self, client, article):
        response = client.get(f'/articles/{article.slug}/')
        assert response.status_code == 200

    def test_draft_returns_404(self, client, db):
        from content.models import Article
        from datetime import date
        Article.objects.create(
            title='Draft Article', slug='draft-article', category='Article',
            author='Author', pub_date=date(2026, 1, 1), status='draft',
        )
        response = client.get('/articles/draft-article/')
        assert response.status_code == 404

    def test_nonexistent_returns_404(self, client):
        response = client.get('/articles/does-not-exist/')
        assert response.status_code == 404

    def test_education_article_url(self, client, db):
        from content.models import Article
        from datetime import date
        Article.objects.create(
            title='Core Ideas Article', slug='core-ideas-test',
            category='Core Ideas', layout='simplified',
            author='Author', pub_date=date(2026, 1, 1),
        )
        response = client.get('/education/articles/core-ideas-test/')
        assert response.status_code == 200


class TestBriefingDetail:
    def test_returns_200(self, client, briefing):
        response = client.get(f'/research/briefings/{briefing.slug}/')
        assert response.status_code == 200

    def test_draft_briefing_returns_404(self, client, db):
        from content.models import Briefing
        from datetime import date
        Briefing.objects.create(
            title='Draft Briefing', slug='draft-briefing',
            author='Author', pub_date=date(2026, 1, 1), draft=True,
        )
        response = client.get('/research/briefings/draft-briefing/')
        assert response.status_code == 404

    def test_nonexistent_returns_404(self, client):
        response = client.get('/research/briefings/does-not-exist/')
        assert response.status_code == 404


class TestNewsDetail:
    def test_returns_200(self, client, news):
        response = client.get(f'/news/{news.slug}/')
        assert response.status_code == 200

    def test_nonexistent_returns_404(self, client):
        response = client.get('/news/does-not-exist/')
        assert response.status_code == 404


class TestLocalGroupDetail:
    def test_returns_200(self, client, local_group):
        response = client.get(f'/local-group/{local_group.slug}/')
        assert response.status_code == 200

    def test_inactive_group_returns_404(self, client, db):
        from content.models import LocalGroup
        LocalGroup.objects.create(
            name='Inactive', slug='inactive-group',
            title='Inactive Group', tagline='Inactive',
            active=False, status='published',
        )
        response = client.get('/local-group/inactive-group/')
        assert response.status_code == 404

    def test_nonexistent_returns_404(self, client):
        response = client.get('/local-group/does-not-exist/')
        assert response.status_code == 404


class TestLocalNewsDetail:
    def test_returns_200(self, client, local_news):
        group_slug = local_news.local_group.slug
        response = client.get(f'/local-group/{group_slug}/{local_news.slug}/')
        assert response.status_code == 200

    def test_nonexistent_returns_404(self, client, local_group):
        response = client.get(f'/local-group/{local_group.slug}/nonexistent/')
        assert response.status_code == 404


# --- Redirects ---

class TestRedirects:
    @pytest.mark.parametrize('old_url,new_url', [
        ('/job-guarantee/', '/research/job-guarantee/'),
        ('/library/', '/education/'),
        ('/ecosystem/', '/'),
        ('/ecosystem/some-org/', '/'),
    ])
    def test_permanent_redirect(self, client, old_url, new_url):
        response = client.get(old_url)
        assert response.status_code == 301, f'{old_url} returned {response.status_code}'
        assert response.url == new_url


# --- CMS protected ---

class TestCMSRequiresAuth:
    @pytest.mark.parametrize('url', [
        '/cms/',
        '/cms/new/',
        '/cms/content/',
        '/cms/pending/',
        '/cms/pages/',
        '/cms/activity/',
    ])
    def test_redirects_to_login(self, client, url):
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.url
