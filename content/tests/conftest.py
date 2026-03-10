"""Shared fixtures for content app tests."""

import pytest
from datetime import date, timedelta

from django.test import Client

from content.models import (
    Article, Briefing, News, Bio, LocalGroup, LocalEvent, LocalNews,
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def local_group(db):
    return LocalGroup.objects.create(
        name='Brighton', slug='brighton', title='MMTUK Brighton',
        tagline='Brighton and Hove local group', active=True,
        status='published',
    )


@pytest.fixture
def article(db):
    return Article.objects.create(
        title='Test Article', slug='test-article', category='Article',
        author='Test Author', pub_date=date(2026, 1, 15),
        body='Article body content.', status='published',
    )


@pytest.fixture
def briefing(db):
    return Briefing.objects.create(
        title='Test Briefing', slug='test-briefing', author='Test Author',
        pub_date=date(2026, 1, 10), body='Briefing body content.',
        status='published', draft=False,
    )


@pytest.fixture
def news(db):
    return News.objects.create(
        title='Test News', slug='test-news', date=date(2026, 2, 1),
        category='Announcement', body='News body content.',
        status='published',
    )


@pytest.fixture
def bio(db):
    return Bio.objects.create(
        name='Jane Doe', slug='jane-doe', role='Researcher',
        body='Bio body.', status='published',
    )


@pytest.fixture
def future_event(local_group):
    return LocalEvent.objects.create(
        title='Future Meetup', slug='future-meetup',
        local_group=local_group,
        date=date.today() + timedelta(days=30),
        tag='Meetup', location='Brighton Library',
        description='A future meetup.', status='published',
    )


@pytest.fixture
def local_news(local_group):
    return LocalNews.objects.create(
        heading='Brighton Update', slug='brighton-update',
        text='Update text.', local_group=local_group,
        date=date(2026, 2, 15), body='Local news body.',
        status='published',
    )
