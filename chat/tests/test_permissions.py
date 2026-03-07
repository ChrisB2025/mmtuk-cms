"""Unit tests for accounts/models.py UserProfile permission methods."""

import pytest


pytestmark = pytest.mark.django_db


class TestCanCreate:

    def test_admin_can_create_everything(self, admin_user):
        p = admin_user.profile
        for ct in ('article', 'briefing', 'news', 'bio', 'ecosystem',
                    'local_event', 'local_news', 'local_group'):
            assert p.can_create(ct), f'admin should create {ct}'

    def test_editor_can_create_most(self, editor_user):
        p = editor_user.profile
        for ct in ('article', 'briefing', 'news', 'local_event', 'local_news', 'ecosystem'):
            assert p.can_create(ct), f'editor should create {ct}'

    def test_editor_cannot_create_bio_or_local_group(self, editor_user):
        p = editor_user.profile
        assert not p.can_create('bio')
        assert not p.can_create('local_group')

    def test_group_lead_can_create_local_only(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert p.can_create('local_event')
        assert p.can_create('local_news')
        assert not p.can_create('article')
        assert not p.can_create('briefing')
        assert not p.can_create('bio')

    def test_contributor_can_create_subset(self, contributor_user):
        p = contributor_user.profile
        for ct in ('article', 'briefing', 'news', 'local_event', 'local_news'):
            assert p.can_create(ct), f'contributor should create {ct}'
        assert not p.can_create('bio')
        assert not p.can_create('ecosystem')
        assert not p.can_create('local_group')


class TestCanPublishDirectly:

    def test_admin_publishes_everything(self, admin_user):
        p = admin_user.profile
        for ct in ('article', 'briefing', 'news', 'bio', 'ecosystem',
                    'local_event', 'local_news', 'local_group'):
            assert p.can_publish_directly(ct), f'admin should publish {ct}'

    def test_editor_publishes_most(self, editor_user):
        p = editor_user.profile
        for ct in ('article', 'briefing', 'news', 'local_event', 'local_news', 'ecosystem'):
            assert p.can_publish_directly(ct), f'editor should publish {ct}'

    def test_editor_cannot_publish_bio_or_local_group(self, editor_user):
        p = editor_user.profile
        assert not p.can_publish_directly('bio')
        assert not p.can_publish_directly('local_group')

    def test_group_lead_publishes_own_group_local(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert p.can_publish_directly('local_event', local_group='brighton')
        assert p.can_publish_directly('local_news', local_group='brighton')

    def test_group_lead_cannot_publish_other_group(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert not p.can_publish_directly('local_event', local_group='oxford')
        assert not p.can_publish_directly('local_news', local_group='oxford')

    def test_group_lead_cannot_publish_non_local(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert not p.can_publish_directly('article')
        assert not p.can_publish_directly('briefing')

    def test_contributor_cannot_publish(self, contributor_user):
        p = contributor_user.profile
        for ct in ('article', 'briefing', 'news', 'bio', 'local_event', 'local_news'):
            assert not p.can_publish_directly(ct), f'contributor should not publish {ct}'


class TestCanEdit:

    def test_admin_edits_everything(self, admin_user):
        assert admin_user.profile.can_edit('article')
        assert admin_user.profile.can_edit('bio')

    def test_editor_edits_everything(self, editor_user):
        assert editor_user.profile.can_edit('article')
        assert editor_user.profile.can_edit('bio')

    def test_group_lead_edits_own_group_local(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert p.can_edit('local_event', local_group='brighton')
        assert p.can_edit('local_news', local_group='brighton')
        assert not p.can_edit('article')

    def test_contributor_cannot_edit(self, contributor_user):
        assert not contributor_user.profile.can_edit('article')
        assert not contributor_user.profile.can_edit('local_event')


class TestCanDelete:

    def test_admin_deletes(self, admin_user):
        assert admin_user.profile.can_delete('article')

    def test_editor_deletes(self, editor_user):
        assert editor_user.profile.can_delete('article')

    def test_group_lead_cannot_delete(self, group_lead_brighton):
        assert not group_lead_brighton.profile.can_delete('local_event')

    def test_contributor_cannot_delete(self, contributor_user):
        assert not contributor_user.profile.can_delete('article')


class TestCanApprove:

    def test_admin_approves_all(self, admin_user):
        assert admin_user.profile.can_approve()

    def test_editor_approves_all(self, editor_user):
        assert editor_user.profile.can_approve()

    def test_group_lead_approves_own_group(self, group_lead_brighton):
        p = group_lead_brighton.profile
        assert p.can_approve('local_event', local_group='brighton')
        assert not p.can_approve('local_event', local_group='oxford')
        assert not p.can_approve('article', local_group='brighton')

    def test_contributor_cannot_approve(self, contributor_user):
        assert not contributor_user.profile.can_approve()
