import json
import re
from datetime import date
from pathlib import Path

import markdown
from django.shortcuts import render
from django.templatetags.static import static

from content.models import Bio, Briefing, LocalEvent, News

DATA_DIR = Path(__file__).resolve().parent / 'data' / 'pages'

IMG_PREFIX = 'content/images/homepage/'


def _static_image_url(path):
    """Convert /images/xxx to Django static URL for content/images/xxx."""
    if path and path.startswith('/images/'):
        return static('content/images/' + path[8:])
    return path or static('content/images/placeholder-image.svg')


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


def briefings_index(request):
    briefings = list(
        Briefing.objects.filter(status='published', draft=False)
        .order_by('-pub_date')
    )
    featured = None
    remaining = []
    if briefings:
        featured = next((b for b in briefings if b.featured), briefings[0])
        remaining = [b for b in briefings if b.pk != featured.pk]
        featured.thumbnail_url = _static_image_url(featured.thumbnail)
        for b in remaining:
            b.thumbnail_url = _static_image_url(b.thumbnail)
    return render(request, 'content/briefings.html', {
        'featured_briefing': featured,
        'briefings': remaining,
        'has_briefings': bool(briefings),
        'hero_image': static('content/images/homepage/briefing-room.avif'),
        'hero_srcset': ' '.join([
            static('content/images/homepage/briefing-room-p-500.avif') + ' 500w,',
            static('content/images/homepage/briefing-room-p-800.avif') + ' 800w,',
            static('content/images/homepage/briefing-room.avif') + ' 1920w',
        ]),
        'meta': {
            'title': 'MMT Briefings',
            'description': 'Critiques and rebuttals of public economic commentary from MMTUK affiliated authors.',
        },
    })


def research(request):
    data = _load_page_data('research.json')
    briefings = list(
        Briefing.objects.filter(status='published', draft=False)
        .order_by('-pub_date')[:3]
    )
    hero_briefing = briefings[0] if briefings else None
    smaller_briefings = briefings[1:3]
    if hero_briefing:
        hero_briefing.thumbnail_url = _static_image_url(hero_briefing.thumbnail)
    for b in smaller_briefings:
        b.thumbnail_url = _static_image_url(b.thumbnail)

    approach_cards = [
        {'heading': data['approach'][f'card_{i}_heading'],
         'body': data['approach'][f'card_{i}_body']}
        for i in range(1, 6)
    ]

    return render(request, 'content/research.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'policy_areas': data['policy_areas'],
        'jg': data['job_guarantee'],
        'jg_image': static('content/images/homepage/adult-education.avif'),
        'zirp': data['zirp'],
        'zirp_image': static('content/images/homepage/central-london-banks.avif'),
        'briefings_data': data['briefings'],
        'hero_briefing': hero_briefing,
        'smaller_briefings': smaller_briefings,
        'has_briefings': bool(briefings),
        'approach': data['approach'],
        'approach_cards': approach_cards,
        'hero_image': static('content/images/homepage/briefing-room.avif'),
        'hero_srcset': ' '.join([
            static('content/images/homepage/briefing-room-p-500.avif') + ' 500w,',
            static('content/images/homepage/briefing-room-p-800.avif') + ' 800w,',
            static('content/images/homepage/briefing-room.avif') + ' 1920w',
        ]),
    })


def about_us(request):
    data = _load_page_data('about-us.json')

    news_items = News.objects.filter(status='published').order_by('-date')[:5]
    news_with_body = [
        {'item': n, 'has_body': bool(n.body and n.body.strip())}
        for n in news_items
    ]

    upcoming_events = LocalEvent.objects.filter(
        status='published', date__gt=date.today()
    ).order_by('date')
    for e in upcoming_events:
        e.image_url = _static_image_url(e.image)

    all_bios = list(Bio.objects.filter(status='published'))
    steering_order = data['steering_group']['order']
    steering_group = sorted(
        [b for b in all_bios if b.role != "Advisory Board Member"],
        key=lambda b: steering_order.index(b.name) if b.name in steering_order else 999
    )
    advisory_board = [b for b in all_bios if b.role == "Advisory Board Member"]
    for b in steering_group + advisory_board:
        b.photo_url = _static_image_url(b.photo)

    return render(request, 'content/about_us.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'news_data': data['news'],
        'news_items': news_with_body,
        'events_data': data['events'],
        'upcoming_events': upcoming_events,
        'steering_data': data['steering_group'],
        'steering_group': steering_group,
        'advisory_data': data['advisory_board'],
        'advisory_board': advisory_board,
        'hero_image': static('content/images/pages/UK-Sectoral-balances-clipped.avif'),
        'hero_srcset': ' '.join([
            static('content/images/pages/UK-Sectoral-balances-clipped-p-500.avif') + ' 500w,',
            static('content/images/pages/UK-Sectoral-balances-clipped.avif') + ' 989w',
        ]),
    })


def custom_404(request, exception):
    return render(request, 'content/404.html', status=404)


def custom_401(request, exception):
    return render(request, 'content/401.html', status=403)
