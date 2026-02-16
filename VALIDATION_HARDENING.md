# Validation Hardening - Phase 2, Task #6

**Date:** 2026-02-16
**Status:** ✅ Complete

## Overview

This document describes the validation hardening improvements implemented in Phase 2, Task #6. The goal was to make content validation more robust, provide better error messages, and add comprehensive testing.

---

## What Was Done

### 1. Field-Level Validation Helpers

Created `chat/services/validation_helpers.py` with detailed validation functions:

#### Date Format Validation
```python
from chat.services.validation_helpers import validate_date_format

result = validate_date_format('pubDate', '2026-02-16')
if not result.is_valid:
    print(result)  # Shows error, actual value, expected format, and fix suggestion
```

**Accepts:**
- ISO 8601 datetime strings (`2026-02-16T10:00:00.000Z`)
- Simple date strings (`2026-02-16`)
- Python `date` and `datetime` objects

**Features:**
- Validates date values (catches invalid dates like 2026-13-01)
- Provides clear error messages
- Suggests fixes (e.g., "Check month (01-12) and day (01-31) are valid")

#### Slug Format Validation
```python
result = validate_slug_format('slug', 'My Article')
# Error: Invalid slug: contains uppercase letters, contains spaces
# Fix: convert to lowercase, replace spaces with hyphens (e.g., 'my-article')
```

**Rules:**
- Lowercase letters, numbers, hyphens only
- No spaces, underscores, or special characters
- Cannot start or end with hyphen
- No consecutive hyphens

**Features:**
- Identifies multiple issues at once
- Suggests corrected slug

#### URL Format Validation
```python
result = validate_url_format('website', 'example.com')
# Error: URL must include protocol (http:// or https://)
# Fix: Add https:// prefix: 'https://example.com'
```

**Accepts:**
- Full URLs with `http://` or `https://`
- Relative paths starting with `/` (for internal links)

**Features:**
- Validates URL structure
- Provides helpful fix suggestions

#### Enum Value Validation
```python
allowed_values = ['Article', 'Commentary', 'Research']
result = validate_enum_value('category', 'article', allowed_values)
# Error: Invalid value: not in allowed list
# Fix: Use 'Article' (correct capitalization)
```

**Features:**
- Case-sensitive matching
- Suggests close matches (case-insensitive)
- Shows all allowed values

#### String Length Validation
```python
result = validate_string_length('summary', 'Hi', min_length=10)
# Error: Too short: 2 characters
# Expected: At least 10 characters
# Fix: Add 8 more characters
```

**Features:**
- Min/max length constraints
- Shows how many characters to add/remove

### 2. Enhanced Error Messages

Updated `chat/services/astro_validator.py` to provide detailed error messages:

**Before:**
```
Field 'pubDate': '16-02-2026' is not valid under any of the given schemas
```

**After:**
```
❌ Validation Error:

**pubDate**: '16-02-2026' is not valid under any of the given schemas
  Actual value: '16-02-2026'
  Expected format: date-time
  💡 Use ISO 8601 format: '2026-02-16' or '2026-02-16T10:00:00.000Z'
```

**Features:**
- Shows field path (e.g., `event.registrationLink`)
- Shows actual vs expected value
- Provides context-aware fix suggestions
- Emoji indicators for better visibility
- Shows up to 5 errors at once (not just 3)

### 3. Validation Metrics Tracking

Added metrics tracking to monitor validation performance:

```python
from chat.services.astro_validator import get_validation_metrics

metrics = get_validation_metrics()
# {
#   'article': {
#     'total': 100,
#     'passed': 95,
#     'failed': 5,
#     'total_errors': 12
#   },
#   'briefing': {...},
#   ...
# }
```

**Features:**
- Tracks validation success/failure rates per content type
- Counts total errors across all validations
- 1-hour cache (auto-reset)
- Logs summary every 10th validation
- Management command to view metrics: `python manage.py validation_metrics`

**View Metrics:**
```bash
python manage.py validation_metrics
```

**Output:**
```
=== Validation Metrics (Last Hour) ===

Overall:
  Total validations: 47
  Passed: 45 (95.7%)
  Failed: 2 (4.3%)
  Total errors: 5
  Average errors per failure: 2.5

By Content Type:

  article:
    Total: 20
    Passed: 20 (100.0%)
    Failed: 0 (100% pass rate)

  briefing:
    Total: 15
    Passed: 14 (93.3%)
    Failed: 1 (6.7%)
    Avg errors per failure: 3.0

  ...
```

**Reset Metrics:**
```bash
python manage.py validation_metrics --reset
```

### 4. Comprehensive Test Suite

Created `chat/tests/test_validation.py` with 40 test cases:

**Test Coverage:**
- ✅ Date validation (7 tests)
- ✅ Slug validation (9 tests)
- ✅ URL validation (7 tests)
- ✅ Enum validation (4 tests)
- ✅ String length validation (5 tests)
- ✅ ValidationResult class (2 tests)
- ✅ Edge cases (6 tests)

**Run Tests:**
```bash
python -m pytest chat/tests/test_validation.py -v
```

**Test Categories:**
1. **Valid inputs pass** - Ensures correct values are accepted
2. **Invalid inputs fail** - Ensures incorrect values are rejected
3. **Error messages are helpful** - Validates error message content
4. **Edge cases** - Tests null, empty, whitespace, unicode, very long values
5. **Type safety** - Ensures no auto-coercion happens

---

## API Reference

### ValidationResult Class

```python
class ValidationResult:
    is_valid: bool           # Whether validation passed
    field_name: str          # Name of field being validated
    error_message: str       # Human-readable error message
    actual_value: any        # The value that was validated
    expected_format: str     # Expected format/type
    fix_suggestion: str      # Suggestion for fixing the error

    def __str__(self) -> str:
        """Returns formatted error message for display."""
```

### Validation Functions

```python
# Date validation
validate_date_format(field_name: str, value: any) -> ValidationResult

# Slug validation
validate_slug_format(field_name: str, value: any) -> ValidationResult

# URL validation
validate_url_format(
    field_name: str,
    value: any,
    required: bool = False
) -> ValidationResult

# Enum validation
validate_enum_value(
    field_name: str,
    value: any,
    allowed_values: list
) -> ValidationResult

# String length validation
validate_string_length(
    field_name: str,
    value: any,
    min_length: int = None,
    max_length: int = None
) -> ValidationResult
```

### Metrics Functions

```python
# Get current metrics
get_validation_metrics() -> Dict[str, dict]

# Reset metrics
reset_validation_metrics() -> None

# Track validation result (called automatically)
track_validation_result(
    content_type: str,
    is_valid: bool,
    error_count: int = 0
) -> None
```

---

## Usage Examples

### Example 1: Validate Frontmatter Before Commit

```python
from chat.services.astro_validator import validate_against_astro_schema

frontmatter = {
    'title': 'My Article',
    'slug': 'my-article',
    'category': 'Article',
    'author': 'John Doe',
    'pubDate': '2026-02-16',
}

is_valid, error_message = validate_against_astro_schema('article', frontmatter)

if not is_valid:
    print(error_message)
    # Shows detailed errors with fix suggestions
else:
    # Proceed with commit
    commit_content(frontmatter)
```

### Example 2: Validate Individual Fields

```python
from chat.services.validation_helpers import (
    validate_slug_format,
    validate_date_format
)

# Validate slug
slug_result = validate_slug_format('slug', user_input_slug)
if not slug_result.is_valid:
    # Show error to user
    show_error(str(slug_result))

# Validate date
date_result = validate_date_format('pubDate', user_input_date)
if not date_result.is_valid:
    show_error(str(date_result))
```

### Example 3: Monitor Validation Health

```python
from chat.services.astro_validator import get_validation_metrics

metrics = get_validation_metrics()

for content_type, data in metrics.items():
    pass_rate = 100.0 * data['passed'] / data['total']

    if pass_rate < 90:
        alert_admins(
            f"Low pass rate for {content_type}: {pass_rate:.1f}%"
        )
```

---

## Performance Improvements

### Schema Caching
- Schemas cached for 24 hours (unchanged)
- Metrics cached for 1 hour (new)
- Reduces repeated schema fetches

### Validation Metrics
- Minimal overhead (<1ms per validation)
- Metrics stored in Redis/cache (not database)
- Automatic cleanup after 1 hour

### Error Formatting
- Error messages formatted on-demand
- No performance impact on successful validations
- First 5 errors shown (rest summarized)

---

## Testing

### Run All Validation Tests

```bash
# Run all tests
python -m pytest chat/tests/test_validation.py -v

# Run specific test class
python -m pytest chat/tests/test_validation.py::TestDateValidation -v

# Run with coverage
python -m pytest chat/tests/test_validation.py --cov=chat.services.validation_helpers
```

### Manual Testing

```bash
# Start Django shell
python manage.py shell

# Test validation helpers
from chat.services.validation_helpers import validate_slug_format

result = validate_slug_format('slug', 'My Invalid Slug')
print(result)
```

---

## Error Message Examples

### Invalid Date Format

```
❌ Validation Error:

**pubDate**: '16-02-2026' is not valid under any of the given schemas
  Actual value: '16-02-2026'
  Expected format: date-time
  💡 Use ISO 8601 format: '2026-02-16' or '2026-02-16T10:00:00.000Z'
```

### Invalid Slug

```
❌ Validation Error:

**slug**: Invalid slug: contains uppercase letters, contains spaces
  Actual value: 'My Article Title'
  Expected format: lowercase-with-hyphens (e.g., 'my-article-slug')
  💡 Convert to lowercase, replace spaces with hyphens (e.g., 'my-article-title')
```

### Invalid Enum Value

```
❌ Validation Error:

**category**: Invalid value: not in allowed list
  Actual value: 'article'
  Expected: One of: 'Article', 'Commentary', 'Research', 'Core Ideas', 'Core Insights', 'But what about...?'
  💡 Use 'Article' (correct capitalization)
```

### Missing Required Field

```
❌ Validation Error:

**title**: This field is required and cannot be empty
  💡 This field is required and cannot be empty
```

---

## Files Modified/Created

### New Files
- ✅ `chat/services/validation_helpers.py` (465 lines) - Field-level validators
- ✅ `chat/tests/test_validation.py` (436 lines) - 40 comprehensive tests
- ✅ `chat/tests/__init__.py` - Package init
- ✅ `chat/management/commands/validation_metrics.py` (80 lines) - Metrics command
- ✅ `VALIDATION_HARDENING.md` (this file) - Documentation

### Modified Files
- ✅ `chat/services/astro_validator.py` - Enhanced error formatting, metrics tracking

---

## Next Steps

Validation hardening is complete. Suggested next tasks from Phase 2:

1. **Task #4: Event Lifecycle** (Days 3-4) - Auto-archive past events
2. **Task #5: Removed Content SEO** (Day 5) - Generate 301 redirects

---

## Maintenance

### Adding New Validation Rules

To add a new validation helper:

1. Add function to `chat/services/validation_helpers.py`
2. Return `ValidationResult` with detailed error info
3. Add tests to `chat/tests/test_validation.py`
4. Update this documentation

### Monitoring Validation Health

```bash
# Check metrics daily
python manage.py validation_metrics

# Reset if needed
python manage.py validation_metrics --reset
```

### Debugging Validation Issues

```bash
# Enable debug logging
# In settings.py:
LOGGING = {
    'loggers': {
        'chat.services.astro_validator': {
            'level': 'DEBUG',
        },
    },
}

# View logs
tail -f logs/django.log | grep astro_validator
```

---

## Summary

✅ **Enhanced Error Messages** - Detailed, actionable error messages with fix suggestions
✅ **Field-Level Validators** - Date, slug, URL, enum, string length validation
✅ **Validation Metrics** - Track success rates and identify problem areas
✅ **Comprehensive Tests** - 40 tests covering all validation scenarios
✅ **Documentation** - Complete API reference and usage examples

**Result:** Validation is now much more robust, user-friendly, and maintainable.
