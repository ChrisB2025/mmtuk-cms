import json
import re
from datetime import date
from pathlib import Path

import markdown
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static

from content.models import Article, Bio, Briefing, LocalEvent, LocalGroup, LocalNews, News

DATA_DIR = Path(__file__).resolve().parent / 'data' / 'pages'

IMG_PREFIX = 'content/images/homepage/'


def _static_image_url(path):
    """Convert /images/xxx to Django static URL for content/images/xxx.
    /media/images/xxx paths (persistent volume) are returned as-is.
    Falls back to direct /static/ path for files written after last collectstatic."""
    if path and path.startswith('/media/'):
        return path
    if path and path.startswith('/images/'):
        try:
            return static('content/images/' + path[8:])
        except ValueError:
            return '/static/content/images/' + path[8:]
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


def robots_txt(request):
    host = request.get_host()
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /cms/',
        'Disallow: /admin/',
        '',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def donate(request):
    data = _load_page_data('donate.json')
    site = _load_page_data('site-config.json')
    scheme = site['founder_scheme']
    current = scheme['current_count']
    target = scheme['target_count']
    return render(request, 'content/donate.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'hero_image': static('content/images/pages/Donate-decoration.avif'),
        'hero_srcset': ' '.join([
            static('content/images/pages/matt-seymour-RI1x1DpqEH4-unsplash-p-500.avif') + ' 500w,',
            static('content/images/pages/matt-seymour-RI1x1DpqEH4-unsplash-p-800.avif') + ' 800w,',
            static('content/images/pages/Donate-decoration.avif') + ' 2400w',
        ]),
        'founder_section': data['founder_section'],
        'founder_cta': data['founder_cta'],
        'research_donations': data['research_donations'],
        'pricing': data['pricing'],
        'thank_you': data['thank_you'],
        'stripe_links': site['stripe_links'],
        'deadline_iso': scheme['deadline_iso'],
        'deadline_display': scheme['deadline_display'],
        'milestone_message': scheme['milestone_message'],
        'current_count': current,
        'target_count': target,
        'milestone_percent': min(round(current / target * 100), 100) if target else 0,
    })


def join(request):
    data = _load_page_data('join.json')
    site = _load_page_data('site-config.json')
    return render(request, 'content/join.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'join_section': data['join_section'],
        'form_id': site['action_network_form_id'],
    })


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


def articles_index(request):
    articles = list(
        Article.objects.filter(status='published')
        .order_by('-pub_date')
    )
    for a in articles:
        a.thumbnail_url = _static_image_url(a.thumbnail)
        is_simplified = a.layout in ('simplified', 'rebuttal')
        a.url = f'/education/articles/{a.slug}/' if is_simplified else f'/articles/{a.slug}/'
    return render(request, 'content/articles.html', {
        'articles': articles,
        'hero_image': static('content/images/homepage/Library.avif'),
        'hero_srcset': ' '.join([
            static('content/images/homepage/Library-p-500.avif') + ' 500w,',
            static('content/images/homepage/Library-p-800.avif') + ' 800w,',
            static('content/images/homepage/Library-p-1080.avif') + ' 1080w,',
            static('content/images/homepage/Library.avif') + ' 2400w',
        ]),
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
        if e.local_group:
            e.group_name = e.local_group.title
        else:
            e.group_name = ''

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


def briefing_detail(request, slug):
    briefing = get_object_or_404(Briefing, slug=slug, status='published', draft=False)
    briefing.hero_image_url = _static_image_url(briefing.main_image or briefing.thumbnail)
    body_html = markdown.markdown(briefing.body, extensions=['extra', 'smarty'])
    has_source = bool(briefing.source_title or briefing.source_url)
    return render(request, 'content/briefing_detail.html', {
        'briefing': briefing,
        'body_html': body_html,
        'has_source': has_source,
    })


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug, status='published')
    body_html = markdown.markdown(article.body, extensions=['extra', 'smarty'])
    is_simplified = article.layout in ('simplified', 'rebuttal')
    return render(request, 'content/article_detail.html', {
        'article': article,
        'body_html': body_html,
        'crumb_parent_label': 'Education' if is_simplified else 'Articles',
        'crumb_parent_url': '/education/' if is_simplified else '/articles/',
    })


def news_detail(request, slug):
    news_item = get_object_or_404(News, slug=slug, status='published')
    raw_image = news_item.main_image or news_item.thumbnail
    news_item.hero_image_url = _static_image_url(raw_image) if raw_image else ''
    body_html = markdown.markdown(news_item.body, extensions=['extra', 'smarty'])
    return render(request, 'content/news_detail.html', {
        'news': news_item,
        'body_html': body_html,
    })


def education(request):
    data = _load_page_data('education.json')
    return render(request, 'content/education.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'library': data['library'],
        'what_is_mmt': data['what_is_mmt'],
        'core_insights': data['core_insights'],
        'objections': data['objections'],
        'advisory_services': data['advisory_services'],
        'hero_image': static('content/images/pages/hands-up.avif'),
    })


def community(request):
    data = _load_page_data('community.json')

    local_groups = LocalGroup.objects.filter(
        status='published', active=True
    ).order_by('name')
    for g in local_groups:
        g.header_image_url = _static_image_url(g.header_image)

    upcoming_events = LocalEvent.objects.filter(
        status='published', date__gt=date.today()
    ).order_by('date')
    for e in upcoming_events:
        e.image_url = _static_image_url(e.image)
        if e.local_group:
            e.group_name = e.local_group.title
        else:
            e.group_name = ''

    return render(request, 'content/community.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'local_groups_data': data['local_groups'],
        'local_groups': local_groups,
        'events_data': data['events'],
        'upcoming_events': upcoming_events,
        'discord_data': data['discord'],
        'hero_image': static('content/images/pages/Local-events.avif'),
        'hero_srcset': ' '.join([
            static('content/images/pages/Local-events-p-500.avif') + ' 500w,',
            static('content/images/pages/Local-events-p-800.avif') + ' 800w,',
            static('content/images/pages/Local-events-p-1080.avif') + ' 1080w,',
            static('content/images/pages/Local-events.avif') + ' 1920w',
        ]),
        'discord_image': static('content/images/pages/MMTUK-Discord-2.avif'),
    })


def founders(request):
    data = _load_page_data('founders.json')

    exclusive_pages = [
        {
            'title': 'Launch Event',
            'description': 'Full video recording and transcript from the MMTUK launch event at Friends House, London.',
            'tag': 'Event',
            'url': '/founders/launch-event/',
            'image': static('content/images/pages/Donate-decoration.avif'),
        },
    ]

    return render(request, 'content/founders.html', {
        'meta': data['meta'],
        'hero': data['hero'],
        'perks': data['perks'],
        'exclusive_content': data['exclusive_content'],
        'exclusive_pages': exclusive_pages,
        'cta': data['cta'],
        'hero_image': static('content/images/pages/Donate-decoration.avif'),
        'hero_srcset': ' '.join([
            static('content/images/pages/matt-seymour-RI1x1DpqEH4-unsplash-p-500.avif') + ' 500w,',
            static('content/images/pages/matt-seymour-RI1x1DpqEH4-unsplash-p-800.avif') + ' 800w,',
            static('content/images/pages/Donate-decoration.avif') + ' 2400w',
        ]),
    })


def founders_launch_event(request):
    data = _load_page_data('founders-launch-event.json')
    return render(request, 'content/founders_launch_event.html', {
        'meta': data['meta'],
        'header': data['header'],
        'sidebar': data['sidebar'],
        'video': data['video'],
        'body': data['body'],
        'transcript_url': static('content/docs/launch-event-transcript.pdf'),
    })


def job_guarantee(request):
    data = _load_page_data('job-guarantee.json')
    body_html = markdown.markdown(data['body']['content'], extensions=['extra', 'smarty'])

    contributors = []
    for name in ['Patricia Pino', 'Dr Phil Armstrong', 'Steve Laughton']:
        photo_path = f'/images/bios/{name}.avif'
        contributors.append({
            'name': name,
            'photo_url': _static_image_url(photo_path),
        })

    return render(request, 'content/job_guarantee.html', {
        'meta': data['meta'],
        'header': data['header'],
        'metadata': data['metadata'],
        'body_html': body_html,
        'contributors': contributors,
        'paper_cover': static('content/images/research/JG_pic.webp'),
        'download_url': static('content/images/research/20260222-A_counter-inflationary_job_guarantee_for_the_UK-v1.pdf'),
    })


def local_group_detail(request, slug):
    group = get_object_or_404(LocalGroup, slug=slug, status='published', active=True)
    group.header_image_url = _static_image_url(group.header_image)

    local_news = LocalNews.objects.filter(
        local_group=group, status='published'
    ).order_by('-date')[:4]
    news_items = [
        {
            'item': n,
            'has_body': bool(n.body and n.body.strip()),
            'image_url': _static_image_url(n.image) if n.image else '',
        }
        for n in local_news
    ]

    upcoming_events = LocalEvent.objects.filter(
        local_group=group, status='published', date__gt=date.today()
    ).order_by('date')[:6]
    for e in upcoming_events:
        e.image_url = _static_image_url(e.image)

    leader_paragraphs = []
    if group.leader_intro:
        leader_paragraphs = [p.strip() for p in group.leader_intro.split('\n\n') if p.strip()]

    return render(request, 'content/local_group_detail.html', {
        'group': group,
        'group_url': f'/local-group/{group.slug}/',
        'leader_paragraphs': leader_paragraphs,
        'news_items': news_items,
        'has_news': bool(news_items),
        'upcoming_events': upcoming_events,
        'has_events': bool(upcoming_events),
        'discord_image': static('content/images/pages/MMTUK-Discord-2.avif'),
    })


def local_news_detail(request, group_slug, news_slug):
    news_item = get_object_or_404(
        LocalNews, slug=news_slug, local_group__slug=group_slug, status='published'
    )
    group = news_item.local_group
    body_html = markdown.markdown(news_item.body, extensions=['extra', 'smarty'])
    return render(request, 'content/local_news_detail.html', {
        'news': news_item,
        'group': group,
        'group_url': f'/local-group/{group.slug}/',
        'body_html': body_html,
    })


def custom_404(request, exception):
    return render(request, 'content/404.html', status=404)


def custom_401(request, exception):
    return render(request, 'content/401.html', status=403)
