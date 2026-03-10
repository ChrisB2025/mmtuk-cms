"""Root conftest — override static file storage for all tests."""

import django.conf


def pytest_configure(config):
    """Use simple static file storage in tests (no manifest required)."""
    settings = django.conf.settings
    if hasattr(settings, 'STORAGES'):
        settings.STORAGES['staticfiles'] = {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        }
