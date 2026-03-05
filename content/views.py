import json
from pathlib import Path

import markdown
from django.shortcuts import render

DATA_DIR = Path(__file__).resolve().parent / 'data' / 'pages'


def _load_page_data(filename):
    with open(DATA_DIR / filename, encoding='utf-8') as f:
        return json.load(f)


def homepage(request):
    return render(request, 'content/homepage.html')


def privacy_policy(request):
    data = _load_page_data('privacy-policy.json')
    content = data['content']
    return render(request, 'content/privacy_policy.html', {
        'title': content['title'],
        'last_updated': content['last_updated'],
        'body_html': markdown.markdown(content['body']),
    })


def terms_of_engagement(request):
    data = _load_page_data('terms-of-engagement.json')
    content = data['content']
    return render(request, 'content/terms_of_engagement.html', {
        'title': content['title'],
        'last_updated': content['last_updated'],
        'body_html': markdown.markdown(content['body']),
    })


def cookie_preferences(request):
    data = _load_page_data('cookie-preferences.json')
    content = data['content']
    return render(request, 'content/cookie_preferences.html', {
        'title': content['title'],
        'last_updated': content['last_updated'],
        'intro_html': markdown.markdown(content['intro']),
        'services_html': markdown.markdown(content['services_list']),
    })


def custom_404(request, exception):
    return render(request, 'content/404.html', status=404)


def custom_401(request, exception):
    return render(request, 'content/401.html', status=403)
