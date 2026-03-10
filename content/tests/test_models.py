"""Tests for content models — creation, constraints, and string representations."""

from datetime import date

import pytest
from django.db import IntegrityError

from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)

pytestmark = pytest.mark.django_db


class TestArticle:
    def test_create(self, article):
        assert article.pk is not None
        assert article.title == 'Test Article'

    def test_str(self, article):
        assert str(article) == 'Test Article'

    def test_slug_unique(self, article):
        with pytest.raises(IntegrityError):
            Article.objects.create(
                title='Duplicate', slug='test-article', category='Article',
                author='Author', pub_date=date(2026, 1, 1),
            )

    def test_ordering(self, db):
        a1 = Article.objects.create(
            title='Older', slug='older', category='Article',
            author='A', pub_date=date(2025, 1, 1),
        )
        a2 = Article.objects.create(
            title='Newer', slug='newer', category='Article',
            author='A', pub_date=date(2026, 6, 1),
        )
        articles = list(Article.objects.all())
        assert articles[0] == a2  # newer first

    def test_default_status(self, db):
        a = Article.objects.create(
            title='New', slug='new', category='Article',
            author='A', pub_date=date(2026, 1, 1),
        )
        assert a.status == 'published'


class TestBriefing:
    def test_create(self, briefing):
        assert briefing.pk is not None

    def test_str(self, briefing):
        assert str(briefing) == 'Test Briefing'

    def test_slug_unique(self, briefing):
        with pytest.raises(IntegrityError):
            Briefing.objects.create(
                title='Dup', slug='test-briefing', author='A',
                pub_date=date(2026, 1, 1),
            )

    def test_draft_default_false(self, briefing):
        assert briefing.draft is False


class TestNews:
    def test_create(self, news):
        assert news.pk is not None

    def test_str(self, news):
        assert str(news) == 'Test News'

    def test_slug_unique(self, news):
        with pytest.raises(IntegrityError):
            News.objects.create(
                title='Dup', slug='test-news', date=date(2026, 1, 1),
                category='Announcement',
            )


class TestBio:
    def test_create(self, bio):
        assert bio.pk is not None

    def test_str(self, bio):
        assert str(bio) == 'Jane Doe'

    def test_advisory_board_default(self, bio):
        assert bio.advisory_board is False


class TestLocalGroup:
    def test_create(self, local_group):
        assert local_group.pk is not None

    def test_str(self, local_group):
        assert str(local_group) == 'Brighton'

    def test_slug_unique(self, local_group):
        with pytest.raises(IntegrityError):
            LocalGroup.objects.create(
                name='Dup', slug='brighton', title='Dup', tagline='Dup',
            )


class TestLocalEvent:
    def test_create(self, future_event):
        assert future_event.pk is not None

    def test_str(self, future_event):
        assert str(future_event) == 'Future Meetup'

    def test_group_fk(self, future_event, local_group):
        assert future_event.local_group == local_group

    def test_protect_on_group_delete(self, future_event):
        """Deleting a group with events should raise ProtectedError."""
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            future_event.local_group.delete()

    def test_archived_default_false(self, future_event):
        assert future_event.archived is False


class TestLocalNews:
    def test_create(self, local_news):
        assert local_news.pk is not None

    def test_str(self, local_news):
        assert str(local_news) == 'Brighton Update'

    def test_group_fk(self, local_news, local_group):
        assert local_news.local_group == local_group

    def test_protect_on_group_delete(self, local_news):
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            local_news.local_group.delete()


class TestEcosystemEntry:
    def test_create(self, db):
        e = EcosystemEntry.objects.create(
            name='Test Org', slug='test-org',
        )
        assert e.pk is not None
        assert str(e) == 'Test Org'

    def test_default_status_draft(self, db):
        e = EcosystemEntry.objects.create(
            name='Draft Org', slug='draft-org',
        )
        assert e.status == 'draft'

    def test_types_default_empty_list(self, db):
        e = EcosystemEntry.objects.create(
            name='No Types', slug='no-types',
        )
        assert e.types == []
