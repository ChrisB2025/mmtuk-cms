from django.conf import settings


def site_config(request):
    return {
        'SITE_URL': getattr(settings, 'SITE_URL', 'https://mmtuk.org'),
        'LOGO_URL': getattr(settings, 'LOGO_URL', 'https://mmtuk.org/static/content/images/mmtuk-logo.webp'),
    }
