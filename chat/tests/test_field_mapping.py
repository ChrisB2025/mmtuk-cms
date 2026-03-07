"""Unit tests for chat/services/field_mapping.py."""

import pytest
from datetime import date, datetime

from chat.services.field_mapping import (
    camel_to_snake, snake_to_camel, get_model_class, get_title_field,
    auto_layout, generate_slug, instance_to_frontmatter, FIELD_MAP,
)
from content.models import LocalGroup, Article


pytestmark = pytest.mark.django_db


class TestCamelToSnake:

    def test_basic_mapping(self):
        result = camel_to_snake({'pubDate': '2026-01-15', 'readTime': 5})
        assert 'pub_date' in result
        assert 'read_time' in result
        assert result['read_time'] == 5

    def test_unmapped_keys_pass_through(self):
        result = camel_to_snake({'title': 'Hello', 'slug': 'hello'})
        assert result['title'] == 'Hello'
        assert result['slug'] == 'hello'

    def test_none_values_stripped(self):
        result = camel_to_snake({'title': 'Keep', 'author': None})
        assert 'title' in result
        assert 'author' not in result

    def test_empty_string_stripped(self):
        result = camel_to_snake({'title': 'Keep', 'author': ''})
        assert 'author' not in result

    def test_none_string_stripped(self):
        result = camel_to_snake({'title': 'Keep', 'author': 'None'})
        assert 'author' not in result

    def test_whitespace_stripped(self):
        result = camel_to_snake({'title': '  Hello  '})
        assert result['title'] == 'Hello'

    def test_whitespace_only_stripped(self):
        result = camel_to_snake({'title': 'Keep', 'author': '   '})
        assert 'author' not in result

    def test_fk_resolution_by_slug(self, local_group_brighton):
        result = camel_to_snake({'localGroup': 'brighton'})
        assert result['local_group'] == local_group_brighton

    def test_fk_resolution_not_found(self):
        with pytest.raises(ValueError, match='no LocalGroup with slug'):
            camel_to_snake({'localGroup': 'nonexistent'})

    def test_fk_resolution_null(self):
        result = camel_to_snake({'localGroup': None, 'title': 'Keep'})
        assert 'local_group' not in result

    def test_fk_resolution_already_instance(self, local_group_brighton):
        result = camel_to_snake({'localGroup': local_group_brighton})
        assert result['local_group'] is local_group_brighton

    def test_date_parsing_iso_with_time(self):
        result = camel_to_snake({'pubDate': '2026-01-15T00:00:00.000Z'})
        assert result['pub_date'] == date(2026, 1, 15)

    def test_date_parsing_simple(self):
        result = camel_to_snake({'pubDate': '2026-01-15'})
        assert result['pub_date'] == date(2026, 1, 15)

    def test_date_parsing_python_date(self):
        d = date(2026, 1, 15)
        result = camel_to_snake({'pubDate': d})
        assert result['pub_date'] == d

    def test_date_parsing_python_datetime(self):
        dt = datetime(2026, 1, 15, 10, 30)
        result = camel_to_snake({'pubDate': dt})
        assert result['pub_date'] == date(2026, 1, 15)

    def test_all_field_map_keys_convert(self):
        """Every non-FK key in FIELD_MAP should map to its snake_case equivalent."""
        # Skip FK fields (localGroup) which require DB lookup
        skip_keys = {'localGroup'}
        for camel, snake in FIELD_MAP.items():
            if camel in skip_keys:
                continue
            result = camel_to_snake({camel: 'test_value'})
            assert snake in result


class TestSnakeToCamel:

    def test_reverse_mapping(self):
        result = snake_to_camel({'pub_date': date(2026, 1, 15), 'read_time': 5})
        assert 'pubDate' in result
        assert 'readTime' in result

    def test_internal_fields_skipped(self):
        result = snake_to_camel({
            'id': 1, 'created_at': 'x', 'updated_at': 'y', 'status': 'published',
            'title': 'Keep',
        })
        assert 'id' not in result
        assert 'created_at' not in result
        assert 'updated_at' not in result
        assert 'status' not in result
        assert result['title'] == 'Keep'

    def test_fk_instance_to_slug(self, local_group_brighton):
        result = snake_to_camel({'local_group': local_group_brighton})
        assert result['localGroup'] == 'brighton'

    def test_date_to_iso_string(self):
        result = snake_to_camel({'pub_date': date(2026, 1, 15)})
        assert result['pubDate'] == '2026-01-15T00:00:00.000Z'


class TestGetModelClass:

    def test_valid_types(self):
        from content.models import Article, Briefing, News, Bio
        assert get_model_class('article') is Article
        assert get_model_class('briefing') is Briefing
        assert get_model_class('news') is News
        assert get_model_class('bio') is Bio

    def test_invalid_type(self):
        with pytest.raises(ValueError, match='Unknown content type'):
            get_model_class('invalid')


class TestGetTitleField:

    def test_local_news_uses_heading(self):
        assert get_title_field('local_news') == 'heading'

    def test_bio_uses_name(self):
        assert get_title_field('bio') == 'name'

    def test_ecosystem_uses_name(self):
        assert get_title_field('ecosystem') == 'name'

    def test_default_is_title(self):
        assert get_title_field('article') == 'title'
        assert get_title_field('briefing') == 'title'
        assert get_title_field('news') == 'title'


class TestAutoLayout:

    def test_core_ideas_simplified(self):
        assert auto_layout('Core Ideas') == 'simplified'

    def test_core_insights_simplified(self):
        assert auto_layout('Core Insights') == 'simplified'

    def test_rebuttal(self):
        assert auto_layout('But what about...?') == 'rebuttal'

    def test_default(self):
        assert auto_layout('Article') == 'default'
        assert auto_layout('Commentary') == 'default'


class TestGenerateSlug:

    def test_basic(self):
        assert generate_slug('My Test Article') == 'my-test-article'

    def test_special_chars_removed(self):
        assert generate_slug('What about...?') == 'what-about'

    def test_leading_trailing_hyphens_stripped(self):
        assert generate_slug('  --Hello World--  ') == 'hello-world'


class TestInstanceToFrontmatter:

    def test_article_round_trip(self, sample_article):
        fm = instance_to_frontmatter('article', sample_article)
        assert fm['title'] == 'Test Article'
        assert fm['slug'] == 'test-article'
        assert 'pubDate' in fm  # should be camelCase
        assert 'id' not in fm
        assert 'created_at' not in fm

    def test_local_news_uses_heading(self, sample_local_news):
        fm = instance_to_frontmatter('local_news', sample_local_news)
        assert fm['heading'] == 'Brighton Update'

    def test_fk_serialised_as_slug(self, sample_local_event):
        fm = instance_to_frontmatter('local_event', sample_local_event)
        assert fm['localGroup'] == 'brighton'
