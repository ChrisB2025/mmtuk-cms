import json
import re
from pathlib import Path

import markdown
from django.shortcuts import render
from django.templatetags.static import static

DATA_DIR = Path(__file__).resolve().parent / 'data' / 'pages'

IMG_PREFIX = 'content/images/homepage/'


def _load_page_data(filename):
    with open(DATA_DIR / filename, encoding='utf-8') as f:
        return json.load(f)


def _resolve_image(image):
    """Add full static URL to image src and srcset fields."""
    if not image:
        return image
    image = dict(image)
    image['src'] = static(IMG_PREFIX + image['src'])
    if 'srcset' in image:
        image['srcset'] = re.sub(
            r'([^\s,]+\.\w+)',
            lambda m: static(IMG_PREFIX + m.group(1)),
            image['srcset'],
        )
    return image


def homepage(request):
    data = _load_page_data('home.json')
    hero = data['hero']
    for slide in hero['slides']:
        slide['image'] = _resolve_image(slide.get('image'))
    for section_key in ('research_section', 'education_section', 'community_section'):
        for card in data[section_key]['cards']:
            card['image'] = _resolve_image(card.get('image'))
    return render(request, 'content/homepage.html', {
        'hero': hero,
        'research': data['research_section'],
        'education': data['education_section'],
        'community': data['community_section'],
        'testimonials': data['testimonials']['items'],
        'contact': data['contact'],
        'meta': data['meta'],
    })


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
