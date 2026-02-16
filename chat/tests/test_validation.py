"""
Comprehensive test suite for content validation.

Tests validation helpers, schema validation, error messages, and edge cases.
"""

import pytest
from datetime import date, datetime
from chat.services.validation_helpers import (
    validate_date_format,
    validate_slug_format,
    validate_url_format,
    validate_enum_value,
    validate_string_length,
    ValidationResult
)


class TestDateValidation:
    """Test date format validation."""

    def test_valid_iso_datetime(self):
        """Valid ISO 8601 datetime strings pass."""
        result = validate_date_format('pubDate', '2026-02-16T10:00:00.000Z')
        assert result.is_valid

        result = validate_date_format('pubDate', '2026-02-16T10:00:00Z')
        assert result.is_valid

    def test_valid_simple_date(self):
        """Valid simple date strings (YYYY-MM-DD) pass."""
        result = validate_date_format('pubDate', '2026-02-16')
        assert result.is_valid

        result = validate_date_format('pubDate', '2024-01-01')
        assert result.is_valid

    def test_valid_python_date_objects(self):
        """Python date and datetime objects pass."""
        result = validate_date_format('pubDate', date(2026, 2, 16))
        assert result.is_valid

        result = validate_date_format('pubDate', datetime(2026, 2, 16, 10, 0, 0))
        assert result.is_valid

    def test_invalid_date_format(self):
        """Invalid date formats fail with helpful messages."""
        result = validate_date_format('pubDate', '16-02-2026')
        assert not result.is_valid
        assert 'YYYY-MM-DD' in result.expected_format

        result = validate_date_format('pubDate', '2026/02/16')
        assert not result.is_valid

        result = validate_date_format('pubDate', 'February 16, 2026')
        assert not result.is_valid

    def test_invalid_date_values(self):
        """Invalid date values (e.g., month 13) fail."""
        result = validate_date_format('pubDate', '2026-13-01')
        assert not result.is_valid
        assert 'month' in result.fix_suggestion.lower() or 'valid' in result.fix_suggestion.lower()

        result = validate_date_format('pubDate', '2026-02-30')
        assert not result.is_valid
        assert 'day' in result.fix_suggestion.lower() or 'valid' in result.fix_suggestion.lower()

    def test_non_string_non_date_fails(self):
        """Non-string, non-date values fail."""
        result = validate_date_format('pubDate', 12345)
        assert not result.is_valid

        result = validate_date_format('pubDate', ['2026-02-16'])
        assert not result.is_valid

    def test_null_values_pass(self):
        """Null/None values pass (for optional fields)."""
        result = validate_date_format('pubDate', None)
        assert result.is_valid


class TestSlugValidation:
    """Test slug format validation."""

    def test_valid_slugs(self):
        """Valid slug formats pass."""
        valid_slugs = [
            'my-article',
            'article-123',
            'test',
            'very-long-slug-with-many-words',
            '2026-budget-analysis',
        ]
        for slug in valid_slugs:
            result = validate_slug_format('slug', slug)
            assert result.is_valid, f"Expected {slug} to be valid"

    def test_uppercase_fails(self):
        """Uppercase letters fail."""
        result = validate_slug_format('slug', 'My-Article')
        assert not result.is_valid
        assert 'uppercase' in result.error_message.lower()
        assert 'lowercase' in result.fix_suggestion.lower()

    def test_spaces_fail(self):
        """Spaces fail."""
        result = validate_slug_format('slug', 'my article')
        assert not result.is_valid
        assert 'spaces' in result.error_message.lower()
        assert 'hyphen' in result.fix_suggestion.lower()

    def test_underscores_fail(self):
        """Underscores fail."""
        result = validate_slug_format('slug', 'my_article')
        assert not result.is_valid
        assert 'underscore' in result.error_message.lower()

    def test_special_characters_fail(self):
        """Special characters fail."""
        invalid_slugs = ['my@article', 'article!', 'test#slug', 'slug%20']
        for slug in invalid_slugs:
            result = validate_slug_format('slug', slug)
            assert not result.is_valid, f"Expected {slug} to fail"

    def test_leading_trailing_hyphens_fail(self):
        """Leading or trailing hyphens fail."""
        result = validate_slug_format('slug', '-my-article')
        assert not result.is_valid

        result = validate_slug_format('slug', 'my-article-')
        assert not result.is_valid

    def test_consecutive_hyphens_fail(self):
        """Consecutive hyphens fail."""
        result = validate_slug_format('slug', 'my--article')
        assert not result.is_valid
        assert 'consecutive' in result.error_message.lower()

    def test_empty_slug_fails(self):
        """Empty slugs fail."""
        result = validate_slug_format('slug', '')
        assert not result.is_valid

        result = validate_slug_format('slug', '   ')
        assert not result.is_valid

    def test_null_slug_fails(self):
        """Null slugs fail (slug is required)."""
        result = validate_slug_format('slug', None)
        assert not result.is_valid

    def test_suggested_slug_generation(self):
        """Invalid slugs suggest corrected versions."""
        result = validate_slug_format('slug', 'My Article Title')
        assert not result.is_valid
        # Should suggest something like 'my-article-title'
        assert 'my-article-title' in result.fix_suggestion.lower()


class TestURLValidation:
    """Test URL format validation."""

    def test_valid_full_urls(self):
        """Valid full URLs pass."""
        valid_urls = [
            'https://example.com',
            'http://example.com',
            'https://example.com/path/to/page',
            'https://subdomain.example.com',
            'https://example.com/path?query=value',
            'https://example.com:8080/path',
        ]
        for url in valid_urls:
            result = validate_url_format('website', url)
            assert result.is_valid, f"Expected {url} to be valid"

    def test_valid_relative_urls(self):
        """Valid relative URLs (internal links) pass."""
        valid_relative = [
            '/articles',
            '/articles/my-article',
            '/path/to/page',
        ]
        for url in valid_relative:
            result = validate_url_format('link', url)
            assert result.is_valid, f"Expected {url} to be valid"

    def test_missing_protocol_fails(self):
        """URLs without protocol fail."""
        result = validate_url_format('website', 'example.com')
        assert not result.is_valid
        assert 'protocol' in result.error_message.lower() or 'http' in result.error_message.lower()
        assert 'https://' in result.fix_suggestion

    def test_invalid_protocol_fails(self):
        """URLs with invalid protocols fail."""
        result = validate_url_format('website', 'ftp://example.com')
        assert not result.is_valid
        assert 'http' in result.error_message.lower()

    def test_empty_relative_path_fails(self):
        """Relative URL with just '/' fails."""
        result = validate_url_format('link', '/')
        assert not result.is_valid

    def test_null_optional_url_passes(self):
        """Null/empty URLs pass if not required."""
        result = validate_url_format('website', None, required=False)
        assert result.is_valid

        result = validate_url_format('website', '', required=False)
        assert result.is_valid

    def test_null_required_url_fails(self):
        """Null URLs fail if required."""
        result = validate_url_format('website', None, required=True)
        assert not result.is_valid

        result = validate_url_format('website', '', required=True)
        assert not result.is_valid


class TestEnumValidation:
    """Test enum value validation."""

    def test_valid_enum_values(self):
        """Values in allowed list pass."""
        allowed = ['Article', 'Commentary', 'Research']

        result = validate_enum_value('category', 'Article', allowed)
        assert result.is_valid

        result = validate_enum_value('category', 'Research', allowed)
        assert result.is_valid

    def test_invalid_enum_value_fails(self):
        """Values not in allowed list fail."""
        allowed = ['Article', 'Commentary', 'Research']

        result = validate_enum_value('category', 'InvalidCategory', allowed)
        assert not result.is_valid
        assert 'Article' in result.expected_format
        assert 'Commentary' in result.expected_format

    def test_case_mismatch_suggests_correction(self):
        """Case mismatches suggest correct capitalization."""
        allowed = ['Article', 'Commentary', 'Research']

        result = validate_enum_value('category', 'article', allowed)
        assert not result.is_valid
        assert 'Article' in result.fix_suggestion  # Should suggest correct capitalization

    def test_null_enum_fails(self):
        """Null enum values fail."""
        allowed = ['Article', 'Commentary']

        result = validate_enum_value('category', None, allowed)
        assert not result.is_valid


class TestStringLengthValidation:
    """Test string length validation."""

    def test_valid_length(self):
        """Strings within length constraints pass."""
        result = validate_string_length('summary', 'Valid summary text', min_length=5, max_length=100)
        assert result.is_valid

    def test_too_short_fails(self):
        """Strings below minimum length fail."""
        result = validate_string_length('summary', 'Hi', min_length=10)
        assert not result.is_valid
        assert 'short' in result.error_message.lower()
        assert '8 more' in result.fix_suggestion  # Need 8 more chars

    def test_too_long_fails(self):
        """Strings above maximum length fail."""
        long_text = 'x' * 150
        result = validate_string_length('summary', long_text, max_length=100)
        assert not result.is_valid
        assert 'long' in result.error_message.lower()
        assert '50' in result.fix_suggestion  # Remove 50 chars

    def test_null_passes(self):
        """Null values pass (for optional fields)."""
        result = validate_string_length('summary', None, min_length=10)
        assert result.is_valid

    def test_non_string_fails(self):
        """Non-string values fail."""
        result = validate_string_length('summary', 12345, min_length=5)
        assert not result.is_valid


class TestValidationResult:
    """Test ValidationResult class."""

    def test_string_representation_valid(self):
        """Valid results format correctly."""
        result = ValidationResult(True, 'test_field')
        output = str(result)
        assert 'test_field' in output
        assert 'valid' in output.lower()

    def test_string_representation_invalid(self):
        """Invalid results show all error details."""
        result = ValidationResult(
            is_valid=False,
            field_name='slug',
            error_message='Contains uppercase',
            actual_value='My-Slug',
            expected_format='lowercase-with-hyphens',
            fix_suggestion='Convert to lowercase'
        )
        output = str(result)

        assert 'slug' in output
        assert 'Contains uppercase' in output
        assert "'My-Slug'" in output
        assert 'lowercase-with-hyphens' in output
        assert 'Convert to lowercase' in output


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_strings(self):
        """Empty strings handled correctly."""
        # Empty slug fails
        result = validate_slug_format('slug', '')
        assert not result.is_valid

        # Empty URL (optional) passes
        result = validate_url_format('website', '', required=False)
        assert result.is_valid

    def test_whitespace_only(self):
        """Whitespace-only strings handled correctly."""
        result = validate_slug_format('slug', '   ')
        assert not result.is_valid

    def test_unicode_characters(self):
        """Unicode characters handled appropriately."""
        # Slugs should only allow ASCII
        result = validate_slug_format('slug', 'café-article')
        assert not result.is_valid

    def test_very_long_values(self):
        """Very long values handled without crashing."""
        long_slug = 'a' * 1000
        result = validate_slug_format('slug', long_slug)
        # Should validate without crashing (may pass or fail depending on rules)
        assert result is not None

    def test_type_coercion(self):
        """Values are not auto-coerced."""
        # Number passed as date should fail
        result = validate_date_format('pubDate', 20260216)
        assert not result.is_valid

        # List passed as string should fail
        result = validate_slug_format('slug', ['my', 'slug'])
        assert not result.is_valid


# Integration tests would go here if we had access to Django test client
# For now, these unit tests cover the validation helpers comprehensively
