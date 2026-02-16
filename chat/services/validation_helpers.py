"""
Field-level validation helpers for content frontmatter.

Provides detailed validation with helpful error messages and fix suggestions.
These validators complement JSON Schema validation with more specific checks.
"""

import re
from datetime import date, datetime
from typing import Tuple, Optional
from urllib.parse import urlparse


class ValidationResult:
    """Result of a field validation with detailed error information."""

    def __init__(self, is_valid: bool, field_name: str, error_message: str = None,
                 actual_value: any = None, expected_format: str = None,
                 fix_suggestion: str = None):
        self.is_valid = is_valid
        self.field_name = field_name
        self.error_message = error_message
        self.actual_value = actual_value
        self.expected_format = expected_format
        self.fix_suggestion = fix_suggestion

    def __str__(self) -> str:
        """Format error message for display."""
        if self.is_valid:
            return f"✓ {self.field_name}: valid"

        parts = [f"✗ {self.field_name}: {self.error_message}"]

        if self.actual_value is not None:
            parts.append(f"  Actual: {repr(self.actual_value)}")

        if self.expected_format:
            parts.append(f"  Expected: {self.expected_format}")

        if self.fix_suggestion:
            parts.append(f"  Fix: {self.fix_suggestion}")

        return '\n'.join(parts)


def validate_date_format(field_name: str, value: any) -> ValidationResult:
    """
    Validate date field is in correct format.

    Accepts:
    - ISO 8601 datetime strings (YYYY-MM-DDTHH:MM:SS.sssZ)
    - Simple date strings (YYYY-MM-DD)
    - Python date/datetime objects

    Args:
        field_name: Name of the field being validated
        value: The value to validate

    Returns:
        ValidationResult with detailed error info if invalid
    """
    if value is None:
        return ValidationResult(True, field_name)

    # Python date/datetime objects are valid
    if isinstance(value, (date, datetime)):
        return ValidationResult(True, field_name)

    # Must be a string for further validation
    if not isinstance(value, str):
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Date must be a string, date, or datetime object",
            actual_value=value,
            expected_format="YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS.sssZ",
            fix_suggestion="Provide date as ISO 8601 string or Python date object"
        )

    # Check for ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SS.sssZ)
    iso_datetime_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$'
    if re.match(iso_datetime_pattern, value):
        try:
            # Validate it's a real date
            if value.endswith('Z'):
                datetime.fromisoformat(value[:-1])
            else:
                datetime.fromisoformat(value)
            return ValidationResult(True, field_name)
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message=f"Invalid ISO datetime: {e}",
                actual_value=value,
                expected_format="YYYY-MM-DDTHH:MM:SS.sssZ",
                fix_suggestion="Check month (01-12) and day (01-31) are valid"
            )

    # Check for simple date format (YYYY-MM-DD)
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if re.match(date_pattern, value):
        try:
            datetime.strptime(value, '%Y-%m-%d')
            return ValidationResult(True, field_name)
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message=f"Invalid date: {e}",
                actual_value=value,
                expected_format="YYYY-MM-DD",
                fix_suggestion="Check month (01-12) and day (01-31) are valid"
            )

    # Invalid format
    return ValidationResult(
        is_valid=False,
        field_name=field_name,
        error_message="Date format not recognized",
        actual_value=value,
        expected_format="YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS.sssZ",
        fix_suggestion="Use format like '2026-02-16' or '2026-02-16T10:00:00.000Z'"
    )


def validate_slug_format(field_name: str, value: any) -> ValidationResult:
    """
    Validate slug is in correct format (lowercase-with-hyphens).

    Valid slugs:
    - All lowercase letters, numbers, hyphens
    - No spaces, underscores, or special characters
    - Cannot start or end with hyphen
    - No consecutive hyphens

    Args:
        field_name: Name of the field being validated
        value: The value to validate

    Returns:
        ValidationResult with detailed error info if invalid
    """
    if value is None:
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Slug is required",
            fix_suggestion="Provide a URL-safe slug (lowercase-with-hyphens)"
        )

    if not isinstance(value, str):
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Slug must be a string",
            actual_value=value,
            expected_format="lowercase-with-hyphens",
            fix_suggestion="Convert to string and use only lowercase, numbers, and hyphens"
        )

    # Check for empty string
    if not value.strip():
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Slug cannot be empty",
            actual_value=value,
            fix_suggestion="Provide a meaningful slug based on the title"
        )

    # Valid slug pattern: lowercase letters, numbers, hyphens (no start/end hyphen, no consecutive hyphens)
    slug_pattern = r'^[a-z0-9]+(-[a-z0-9]+)*$'

    if not re.match(slug_pattern, value):
        issues = []
        suggestions = []

        if value != value.lower():
            issues.append("contains uppercase letters")
            suggestions.append("convert to lowercase")

        if ' ' in value:
            issues.append("contains spaces")
            suggestions.append("replace spaces with hyphens")

        if '_' in value:
            issues.append("contains underscores")
            suggestions.append("replace underscores with hyphens")

        if value.startswith('-') or value.endswith('-'):
            issues.append("starts or ends with hyphen")
            suggestions.append("remove leading/trailing hyphens")

        if '--' in value:
            issues.append("contains consecutive hyphens")
            suggestions.append("use single hyphens only")

        if re.search(r'[^a-z0-9-]', value):
            issues.append("contains special characters")
            suggestions.append("remove special characters")

        error_msg = f"Invalid slug: {', '.join(issues) if issues else 'format not recognized'}"
        fix_msg = ', '.join(suggestions) if suggestions else "Use only lowercase letters, numbers, and hyphens"

        # Generate suggested slug
        suggested = value.lower()
        suggested = re.sub(r'[^a-z0-9-]+', '-', suggested)
        suggested = re.sub(r'-+', '-', suggested)
        suggested = suggested.strip('-')

        if suggested and suggested != value:
            fix_msg += f" (e.g., '{suggested}')"

        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message=error_msg,
            actual_value=value,
            expected_format="lowercase-with-hyphens (e.g., 'my-article-slug')",
            fix_suggestion=fix_msg
        )

    return ValidationResult(True, field_name)


def validate_url_format(field_name: str, value: any, required: bool = False) -> ValidationResult:
    """
    Validate URL is in correct format.

    Accepts:
    - Full URLs with http:// or https://
    - Relative paths starting with / (for internal links)

    Args:
        field_name: Name of the field being validated
        value: The value to validate
        required: Whether the field is required (default False)

    Returns:
        ValidationResult with detailed error info if invalid
    """
    # None/empty is valid if not required
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message="URL is required",
                fix_suggestion="Provide a valid URL starting with http://, https://, or /"
            )
        return ValidationResult(True, field_name)

    if not isinstance(value, str):
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="URL must be a string",
            actual_value=value,
            expected_format="http://example.com or /path/to/page",
            fix_suggestion="Convert to string URL"
        )

    value = value.strip()

    # Allow relative paths (internal links)
    if value.startswith('/'):
        # Simple validation: must have at least one character after /
        if len(value) > 1:
            return ValidationResult(True, field_name)
        else:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message="Relative URL must have a path",
                actual_value=value,
                expected_format="/path/to/page",
                fix_suggestion="Provide a valid path after the / (e.g., '/articles/my-article')"
            )

    # Validate full URLs
    try:
        parsed = urlparse(value)

        # Must have scheme (http/https)
        if not parsed.scheme:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message="URL must include protocol (http:// or https://)",
                actual_value=value,
                expected_format="https://example.com/path",
                fix_suggestion=f"Add https:// prefix: 'https://{value}'"
            )

        # Must be http or https
        if parsed.scheme not in ('http', 'https'):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message=f"URL protocol must be http or https, not {parsed.scheme}",
                actual_value=value,
                expected_format="https://example.com/path",
                fix_suggestion="Use https:// for external links or / for internal links"
            )

        # Must have a domain (netloc)
        if not parsed.netloc:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                error_message="URL must include a domain",
                actual_value=value,
                expected_format="https://example.com/path",
                fix_suggestion="Provide a complete URL with domain (e.g., 'https://example.com')"
            )

        return ValidationResult(True, field_name)

    except Exception as e:
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message=f"Invalid URL: {e}",
            actual_value=value,
            expected_format="https://example.com or /path",
            fix_suggestion="Check URL syntax and formatting"
        )


def validate_enum_value(field_name: str, value: any, allowed_values: list) -> ValidationResult:
    """
    Validate field value is one of the allowed enum values.

    Args:
        field_name: Name of the field being validated
        value: The value to validate
        allowed_values: List of allowed values

    Returns:
        ValidationResult with detailed error info if invalid
    """
    if value is None:
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Value is required",
            expected_format=f"One of: {', '.join(repr(v) for v in allowed_values)}",
            fix_suggestion=f"Choose one of the allowed values"
        )

    if value not in allowed_values:
        # Find similar values (case-insensitive match)
        suggestions = []
        if isinstance(value, str):
            value_lower = value.lower()
            for allowed in allowed_values:
                if isinstance(allowed, str) and allowed.lower() == value_lower:
                    suggestions.append(f"Use '{allowed}' (correct capitalization)")

        # Find close matches (Levenshtein-like)
        if not suggestions and isinstance(value, str):
            for allowed in allowed_values:
                if isinstance(allowed, str) and allowed.lower() in value_lower:
                    suggestions.append(f"Did you mean '{allowed}'?")

        fix_msg = suggestions[0] if suggestions else "Choose from the allowed values listed above"

        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message=f"Invalid value: not in allowed list",
            actual_value=value,
            expected_format=f"One of: {', '.join(repr(v) for v in allowed_values)}",
            fix_suggestion=fix_msg
        )

    return ValidationResult(True, field_name)


def validate_string_length(field_name: str, value: any, min_length: int = None,
                           max_length: int = None) -> ValidationResult:
    """
    Validate string field length constraints.

    Args:
        field_name: Name of the field being validated
        value: The value to validate
        min_length: Minimum length (optional)
        max_length: Maximum length (optional)

    Returns:
        ValidationResult with detailed error info if invalid
    """
    if value is None:
        return ValidationResult(True, field_name)

    if not isinstance(value, str):
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message="Value must be a string",
            actual_value=type(value).__name__,
            fix_suggestion="Convert to string"
        )

    length = len(value)

    if min_length is not None and length < min_length:
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message=f"Too short: {length} characters",
            expected_format=f"At least {min_length} characters",
            fix_suggestion=f"Add {min_length - length} more characters"
        )

    if max_length is not None and length > max_length:
        return ValidationResult(
            is_valid=False,
            field_name=field_name,
            error_message=f"Too long: {length} characters",
            expected_format=f"At most {max_length} characters",
            fix_suggestion=f"Remove {length - max_length} characters"
        )

    return ValidationResult(True, field_name)
