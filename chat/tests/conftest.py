"""Shared fixtures for CMS test suite."""

import pytest
from datetime import date
from django.contrib.auth.models import User
from django.test import Client

from chat.models import Conversation
from content.models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)


# --- User fixtures (one per role) ---

@pytest.fixture
def admin_user(db):
    user = User.objects.create_user('admin', 'admin@test.com', 'testpass')
    user.profile.role = 'admin'
    user.profile.save()
    return user


@pytest.fixture
def editor_user(db):
    user = User.objects.create_user('editor', 'editor@test.com', 'testpass')
    user.profile.role = 'editor'
    user.profile.save()
    return user


@pytest.fixture
def group_lead_brighton(db):
    user = User.objects.create_user('lead_brighton', 'lead@test.com', 'testpass')
    user.profile.role = 'group_lead'
    user.profile.local_group = 'brighton'
    user.profile.save()
    return user


@pytest.fixture
def contributor_user(db):
    user = User.objects.create_user('contributor', 'contrib@test.com', 'testpass')
    # role defaults to 'contributor' from signal, but be explicit
    user.profile.role = 'contributor'
    user.profile.save()
    return user


# --- Authenticated client fixtures ---

@pytest.fixture
def admin_client(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def editor_client(editor_user):
    client = Client()
    client.force_login(editor_user)
    return client


@pytest.fixture
def group_lead_client(group_lead_brighton):
    client = Client()
    client.force_login(group_lead_brighton)
    return client


@pytest.fixture
def contributor_client(contributor_user):
    client = Client()
    client.force_login(contributor_user)
    return client


# --- Content model fixtures ---

@pytest.fixture
def local_group_brighton(db):
    return LocalGroup.objects.create(
        name='Brighton', slug='brighton', title='MMTUK Brighton',
        tagline='Brighton and Hove local group',
    )


@pytest.fixture
def sample_article(db):
    return Article.objects.create(
        title='Test Article', slug='test-article', category='Article',
        author='MMTUK', pub_date=date(2026, 1, 15), body='Test body.',
    )


@pytest.fixture
def sample_briefing(db):
    return Briefing.objects.create(
        title='Test Briefing', slug='test-briefing', author='MMTUK',
        pub_date=date(2026, 1, 10), body='Briefing body.',
    )


@pytest.fixture
def sample_news(db):
    return News.objects.create(
        title='Test News', slug='test-news', date=date(2026, 2, 1),
        category='Announcement', body='News body.',
    )


@pytest.fixture
def sample_bio(db):
    return Bio.objects.create(
        name='Jane Doe', slug='jane-doe', role='Researcher', body='Bio body.',
    )


@pytest.fixture
def sample_ecosystem(db):
    return EcosystemEntry.objects.create(
        name='Test Org', slug='test-org', body='Org body.',
    )


@pytest.fixture
def sample_local_event(local_group_brighton):
    return LocalEvent.objects.create(
        title='Brighton Meetup', slug='brighton-meetup',
        local_group=local_group_brighton, date=date(2026, 3, 1),
        tag='Meetup', location='Brighton Library',
        description='Monthly meetup.',
    )


@pytest.fixture
def sample_local_news(local_group_brighton):
    return LocalNews.objects.create(
        heading='Brighton Update', slug='brighton-update',
        text='Update text.', local_group=local_group_brighton,
        date=date(2026, 2, 15),
    )


@pytest.fixture
def sample_local_group(local_group_brighton):
    """Alias for local_group_brighton."""
    return local_group_brighton


# --- camelCase frontmatter fixtures (what Claude action blocks emit) ---

@pytest.fixture
def article_frontmatter():
    return {
        'title': 'New Article',
        'slug': 'new-article',
        'category': 'Article',
        'author': 'MMTUK',
        'pubDate': '2026-01-15',
    }


@pytest.fixture
def briefing_frontmatter():
    return {
        'title': 'New Briefing',
        'slug': 'new-briefing',
        'author': 'MMTUK',
        'pubDate': '2026-01-10',
    }


@pytest.fixture
def news_frontmatter():
    return {
        'title': 'New News',
        'slug': 'new-news',
        'date': '2026-02-01',
        'category': 'Announcement',
    }


@pytest.fixture
def bio_frontmatter():
    return {
        'name': 'John Smith',
        'slug': 'john-smith',
        'role': 'Advisor',
    }


@pytest.fixture
def ecosystem_frontmatter():
    return {
        'name': 'New Org',
        'slug': 'new-org',
        'activityStatus': 'Active',
    }


@pytest.fixture
def local_group_frontmatter():
    return {
        'name': 'Oxford',
        'slug': 'oxford',
        'title': 'MMTUK Oxford',
        'tagline': 'Oxford local group',
    }


@pytest.fixture
def local_event_frontmatter(local_group_brighton):
    return {
        'title': 'New Event',
        'slug': 'new-event',
        'localGroup': 'brighton',
        'date': '2026-03-15',
        'tag': 'Workshop',
        'location': 'Brighton Hub',
        'description': 'A workshop.',
    }


@pytest.fixture
def local_news_frontmatter(local_group_brighton):
    return {
        'heading': 'New Local News',
        'slug': 'new-local-news',
        'text': 'Some local news text.',
        'localGroup': 'brighton',
        'date': '2026-02-20',
    }


# --- Conversation fixture ---

@pytest.fixture
def conversation(admin_user):
    return Conversation.objects.create(user=admin_user)
