"""Validate all JSON page data files are well-formed and have required keys."""

import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'pages'

# Every page data file that exists
PAGE_FILES = sorted(DATA_DIR.glob('*.json'))


class TestPageDataValid:
    @pytest.mark.parametrize('json_file', PAGE_FILES, ids=lambda p: p.name)
    def test_valid_json(self, json_file):
        """Every JSON file must parse without errors."""
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)
        assert isinstance(data, dict), f'{json_file.name} root should be an object'

    @pytest.mark.parametrize('json_file', PAGE_FILES, ids=lambda p: p.name)
    def test_no_empty_file(self, json_file):
        """No JSON file should be empty."""
        assert json_file.stat().st_size > 2, f'{json_file.name} is empty'


class TestPageDataRequiredKeys:
    """Check required keys for pages that define meta (title/description)."""

    PAGES_WITH_META = [
        'home.json', 'research.json', 'education.json', 'community.json',
        'about-us.json', 'donate.json', 'join.json', 'founders.json',
        'founders-launch-event.json', 'job-guarantee.json',
    ]

    @pytest.mark.parametrize('filename', PAGES_WITH_META)
    def test_has_meta_title(self, filename):
        with open(DATA_DIR / filename, encoding='utf-8') as f:
            data = json.load(f)
        assert 'meta' in data, f'{filename} missing "meta" key'
        assert 'title' in data['meta'], f'{filename} missing "meta.title"'
        assert data['meta']['title'], f'{filename} has empty "meta.title"'

    @pytest.mark.parametrize('filename', PAGES_WITH_META)
    def test_has_meta_description(self, filename):
        with open(DATA_DIR / filename, encoding='utf-8') as f:
            data = json.load(f)
        assert 'description' in data['meta'], f'{filename} missing "meta.description"'
        assert data['meta']['description'], f'{filename} has empty "meta.description"'

    def test_site_config_has_required_keys(self):
        with open(DATA_DIR / 'site-config.json', encoding='utf-8') as f:
            data = json.load(f)
        assert 'stripe_links' in data, 'site-config missing stripe_links'
        assert 'founder_scheme' in data, 'site-config missing founder_scheme'
        assert 'action_network_form_id' in data, 'site-config missing action_network_form_id'

    def test_home_has_hero_slides(self):
        with open(DATA_DIR / 'home.json', encoding='utf-8') as f:
            data = json.load(f)
        assert 'hero' in data, 'home.json missing hero'
        assert 'slides' in data['hero'], 'home.json missing hero.slides'
        assert len(data['hero']['slides']) > 0, 'home.json hero.slides is empty'

    def test_research_has_policy_sections(self):
        with open(DATA_DIR / 'research.json', encoding='utf-8') as f:
            data = json.load(f)
        for key in ('job_guarantee', 'zirp', 'policy_areas', 'briefings'):
            assert key in data, f'research.json missing "{key}"'

    def test_education_has_sections(self):
        with open(DATA_DIR / 'education.json', encoding='utf-8') as f:
            data = json.load(f)
        for key in ('library', 'what_is_mmt', 'core_insights', 'objections'):
            assert key in data, f'education.json missing "{key}"'

    def test_community_has_sections(self):
        with open(DATA_DIR / 'community.json', encoding='utf-8') as f:
            data = json.load(f)
        for key in ('local_groups', 'events', 'discord'):
            assert key in data, f'community.json missing "{key}"'

    def test_donate_has_pricing(self):
        with open(DATA_DIR / 'donate.json', encoding='utf-8') as f:
            data = json.load(f)
        assert 'pricing' in data, 'donate.json missing pricing'
        assert len(data['pricing']) > 0, 'donate.json pricing is empty'

    def test_privacy_policy_has_content(self):
        with open(DATA_DIR / 'privacy-policy.json', encoding='utf-8') as f:
            data = json.load(f)
        assert 'content' in data, 'privacy-policy.json missing content'
        assert 'body' in data['content'], 'privacy-policy.json missing content.body'

    def test_terms_has_content(self):
        with open(DATA_DIR / 'terms-of-engagement.json', encoding='utf-8') as f:
            data = json.load(f)
        assert 'content' in data, 'terms-of-engagement.json missing content'
        assert 'body' in data['content'], 'terms-of-engagement.json missing content.body'
