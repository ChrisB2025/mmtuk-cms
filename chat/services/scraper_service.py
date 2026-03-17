"""
URL scraping for importing content (Substack articles, general URLs).
"""

import json
import re
import logging

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

# Substack URL patterns
_SUBSTACK_RE = re.compile(r'https?://[\w.-]*\.?substack\.com/', re.IGNORECASE)

# User agent for HTTP requests
_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


def _is_safe_url(url):
    """Block private/internal URLs to prevent SSRF."""
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    # Block obvious internal hostnames
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        return False
    if hostname.endswith('.internal') or hostname.endswith('.local'):
        return False
    # Resolve and check for private IPs
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _fetch_html(url):
    """Fetch a URL and return the HTML content."""
    if not _is_safe_url(url):
        raise ValueError(f'URL blocked by SSRF protection: {url}')
    logger.info('fetch_html: start %.100s', url)
    resp = httpx.get(
        url,
        headers={'User-Agent': _USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10),
    )
    resp.raise_for_status()
    logger.info('fetch_html: done status=%d bytes=%d', resp.status_code, len(resp.content))
    return resp.text


def _clean_markdown(text):
    """Clean up markdownified text."""
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip trailing whitespace from lines
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()


def _enforce_h2_only(text):
    """
    Normalize headings: convert H1 and H3+ to H2.
    Briefings should only use h2 — h1 is reserved for the title in frontmatter,
    and h3 renders larger than h2 in the Webflow-derived CSS.
    """
    # Convert H1 to H2 (single # followed by space, not ##)
    text = re.sub(r'^# (?!#)', '## ', text, flags=re.MULTILINE)
    # Convert H3+ to H2
    text = re.sub(r'^#{3,6}\s+', '## ', text, flags=re.MULTILINE)
    return text


def _strip_title_heading(body_md, title):
    """Remove the first heading if it matches the article title (avoids duplication)."""
    if not title:
        return body_md
    clean_title = re.sub(r'\*{1,2}', '', title).strip().lower()
    match = re.match(r'^#{1,2}\s+\*{0,2}(.+?)\*{0,2}\s*$', body_md, re.MULTILINE)
    if match:
        heading_text = re.sub(r'\*{1,2}', '', match.group(1)).strip().lower()
        if heading_text == clean_title or clean_title.startswith(heading_text):
            body_md = body_md[match.end():].lstrip('\n')
    return body_md


def _strip_thumbnail_from_body(body_md, image_url):
    """Remove the first markdown image whose URL matches the thumbnail (avoids duplication)."""
    if not image_url:
        return body_md
    # Try exact match first, then match just the base URL (without query params)
    escaped = re.escape(image_url)
    body_md = re.sub(r'!\[[^\]]*\]\(' + escaped + r'\)\s*', '', body_md, count=1)
    # Also try matching without query string (signed URLs have different params)
    base_url = image_url.split('?')[0]
    if base_url != image_url:
        escaped_base = re.escape(base_url)
        body_md = re.sub(
            r'!\[[^\]]*\]\(' + escaped_base + r'[^)]*\)\s*', '', body_md, count=1
        )
    return body_md


def _preprocess_figures(container):
    """
    Replace <figure> elements with inline image + optional caption, in-place.
    Each figure becomes an <img alt="caption" src="..."> followed by an italic
    caption paragraph. This preserves image position in the document so
    markdownify converts them to standard ![alt](src) markdown syntax.
    """
    for figure in container.find_all('figure'):
        img = figure.find('img')
        caption_el = figure.find('figcaption')
        caption = caption_el.get_text(strip=True) if caption_el else ''

        if img:
            src = img.get('src') or img.get('data-src') or ''
            if src:
                # Replace all img attrs with just src + alt (caption text)
                for attr in list(img.attrs):
                    del img[attr]
                img['src'] = src
                img['alt'] = caption
                figure.replace_with(img)
                if caption:
                    cap_soup = BeautifulSoup(
                        f'<p><em>{caption}</em></p>', 'html.parser'
                    )
                    img.insert_after(cap_soup.find('p'))
            else:
                figure.decompose()
        else:
            figure.decompose()


def _extract_pub_date(soup):
    """
    Extract publication date from HTML using multiple strategies.
    Returns a YYYY-MM-DD string, or '' if no date found.

    Strategies (in order):
    1. <meta property="article:published_time">  (Open Graph)
    2. JSON-LD structured data (Schema.org datePublished)
    3. <time datetime="..."> element
    4. Common meta name tags (date, DC.date, etc.)
    """
    # Strategy 1: article:published_time meta (Open Graph)
    meta_date = soup.find('meta', property='article:published_time')
    if meta_date and meta_date.get('content', ''):
        return meta_date['content'][:10]

    # Strategy 2: JSON-LD structured data (Schema.org)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            ld = json.loads(script.string or '')
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                dp = item.get('datePublished', '')
                if dp:
                    return dp[:10]
        except (json.JSONDecodeError, AttributeError):
            pass

    # Strategy 3: <time datetime="..."> element
    time_el = soup.find('time', attrs={'datetime': True})
    if time_el:
        dt = time_el['datetime']
        if len(dt) >= 10:
            return dt[:10]

    # Strategy 4: Other common meta tags
    for meta_name in ('date', 'DC.date', 'dcterms.date', 'publish_date'):
        meta = soup.find('meta', attrs={'name': meta_name})
        if meta and meta.get('content', ''):
            return meta['content'][:10]

    return ''


def scrape_substack(url):
    """
    Scrape a Substack article and return structured data.
    Returns a dict with title, author, date, publication, image_url, body_markdown, source_url.
    """
    import time as _time
    t0 = _time.monotonic()

    html = _fetch_html(url)
    logger.info('scrape_substack: parse html %d bytes', len(html))
    soup = BeautifulSoup(html, 'html.parser')
    logger.info('scrape_substack: parsed in %.1fs', _time.monotonic() - t0)

    # Extract metadata from og/meta tags
    title = ''
    og_title = soup.find('meta', property='og:title')
    if og_title:
        title = og_title.get('content', '')
    if not title:
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else ''

    author = ''
    meta_author = soup.find('meta', attrs={'name': 'author'})
    if meta_author:
        author = meta_author.get('content', '')

    pub_date = _extract_pub_date(soup)

    publication = ''
    og_site = soup.find('meta', property='og:site_name')
    if og_site:
        publication = og_site.get('content', '')

    image_url = ''
    og_image = soup.find('meta', property='og:image')
    if og_image:
        image_url = og_image.get('content', '')

    # Extract article body — keep container as BS4 object for figure pre-processing
    container = None
    for selector in ['.body.markup', '.available-content', 'article', '.post-content']:
        container = soup.select_one(selector)
        if container:
            break
    if not container:
        container = soup.find('main') or soup.find('article') or soup.body

    if container:
        logger.info('scrape_substack: preprocessing figures at %.1fs', _time.monotonic() - t0)
        _preprocess_figures(container)
        body_html = str(container)
        logger.info('scrape_substack: body_html %d bytes at %.1fs', len(body_html), _time.monotonic() - t0)
    else:
        body_html = ''

    # Convert HTML to markdown — img is now converted (not stripped)
    logger.info('scrape_substack: running markdownify at %.1fs', _time.monotonic() - t0)
    body_md = md(body_html, heading_style='ATX', strip=['figure', 'figcaption'])
    logger.info('scrape_substack: markdownify done, md %d chars at %.1fs', len(body_md), _time.monotonic() - t0)

    # Strip the thumbnail image from body to avoid duplication with frontmatter
    if image_url:
        body_md = _strip_thumbnail_from_body(body_md, image_url)

    # Clean up: remove subscription CTAs, share buttons, navigation links
    for pattern in _CTA_PATTERNS:
        body_md = re.sub(pattern, '', body_md, flags=re.IGNORECASE)

    body_md = _clean_markdown(body_md)
    body_md = _enforce_h2_only(body_md)
    body_md = _strip_title_heading(body_md, title)

    return {
        'title': title,
        'author': author,
        'date': pub_date,
        'publication': publication,
        'image_url': image_url,
        'body_markdown': body_md,
        'source_url': url,
    }


# CTA/navigation patterns to strip from scraped article bodies
_CTA_PATTERNS = [
    r'Subscribe\s*\n',
    r'Share\s*\n',
    r'Thanks for reading.*?\n',
    r'Get more from.*?\n',
    r'\[Subscribe now\].*?\n',
    r'\[Share\].*?\n',
    r'A publication of.*?\n',
    r'\[?←[^\]]*\]\([^)]*\)\s*\n',    # [← Back to Articles](/articles/)
    r'←\s*Back to\s+\w+.*?\n',         # ← Back to Articles
]


# Schema.org types in priority order for extraction
_SCHEMA_TYPES_PRIORITY = ['Event', 'Article', 'NewsArticle', 'BlogPosting', 'WebPage']


def _extract_json_ld(soup):
    """
    Extract structured data from JSON-LD script blocks.

    Searches for Schema.org types (Event, Article, etc.) and returns
    a normalised dict with: title, author, date, image_url, body_markdown.
    Returns None if no useful structured data found.
    """
    candidates = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except (json.JSONDecodeError, TypeError):
            continue

        # Flatten: handle single objects, arrays, and @graph containers
        items = []
        if isinstance(data, list):
            items.extend(data)
        elif isinstance(data, dict):
            if '@graph' in data:
                graph = data['@graph']
                items.extend(graph if isinstance(graph, list) else [graph])
            else:
                items.append(data)

        for item in items:
            schema_type = item.get('@type', '')
            # @type can be a string or list
            if isinstance(schema_type, list):
                schema_type = schema_type[0] if schema_type else ''
            if schema_type in _SCHEMA_TYPES_PRIORITY:
                candidates.append((schema_type, item))

    if not candidates:
        return None

    # Pick best candidate by priority
    priority = {t: i for i, t in enumerate(_SCHEMA_TYPES_PRIORITY)}
    candidates.sort(key=lambda c: priority.get(c[0], 999))
    schema_type, item = candidates[0]

    # Extract common fields
    title = item.get('name') or item.get('headline') or ''
    description = item.get('description') or item.get('articleBody') or ''
    date = ''
    if schema_type == 'Event':
        date = (item.get('startDate') or '')[:10]
    else:
        date = (item.get('datePublished') or '')[:10]

    # Author: can be string, dict, or list
    author = ''
    raw_author = item.get('author') or item.get('organizer')
    if isinstance(raw_author, dict):
        author = raw_author.get('name', '')
    elif isinstance(raw_author, list) and raw_author:
        first = raw_author[0]
        author = first.get('name', '') if isinstance(first, dict) else str(first)
    elif isinstance(raw_author, str):
        author = raw_author

    # Image: can be string, dict, or list
    image_url = ''
    raw_image = item.get('image')
    if isinstance(raw_image, str):
        image_url = raw_image
    elif isinstance(raw_image, dict):
        image_url = raw_image.get('url', '')
    elif isinstance(raw_image, list) and raw_image:
        first = raw_image[0]
        image_url = first.get('url', '') if isinstance(first, dict) else str(first)

    # Build body markdown from description + event-specific fields
    body_parts = []
    if description:
        body_parts.append(description)

    if schema_type == 'Event':
        # Location
        location = item.get('location')
        if isinstance(location, dict):
            loc_name = location.get('name', '')
            address = location.get('address', '')
            if isinstance(address, dict):
                parts = [address.get('streetAddress', ''),
                         address.get('addressLocality', ''),
                         address.get('postalCode', '')]
                address = ', '.join(p for p in parts if p)
            if loc_name or address:
                body_parts.append(f'\n\n**Location:** {loc_name}, {address}' if loc_name and address
                                  else f'\n\n**Location:** {loc_name or address}')

        # Date/time
        start = item.get('startDate', '')
        end = item.get('endDate', '')
        if start:
            body_parts.append(f'\n\n**Date:** {start}')
            if end:
                body_parts.append(f' to {end}')

        # Offers/tickets
        offers = item.get('offers')
        if offers:
            if isinstance(offers, dict):
                offers = [offers]
            if isinstance(offers, list) and offers:
                ticket_lines = []
                for offer in offers:
                    if isinstance(offer, dict):
                        name = offer.get('name', 'Ticket')
                        price = offer.get('price', '')
                        currency = offer.get('priceCurrency', '')
                        if price:
                            ticket_lines.append(f'- {name}: {currency} {price}')
                if ticket_lines:
                    body_parts.append('\n\n**Tickets:**\n' + '\n'.join(ticket_lines))

    body_markdown = ''.join(body_parts).strip()

    if not title and not body_markdown:
        return None

    return {
        'title': title,
        'author': author,
        'date': date,
        'image_url': image_url,
        'body_markdown': body_markdown,
    }


def scrape_general_url(url):
    """
    Scrape a general URL for content import.
    Returns a dict with title, author, date, image_url, body_markdown, source_url.
    """
    html = _fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    title = ''
    og_title = soup.find('meta', property='og:title')
    if og_title:
        title = og_title.get('content', '')
    if not title:
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else ''
    if not title:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

    author = ''
    meta_author = soup.find('meta', attrs={'name': 'author'})
    if meta_author:
        author = meta_author.get('content', '')

    pub_date = _extract_pub_date(soup)

    image_url = ''
    og_image = soup.find('meta', property='og:image')
    if og_image:
        image_url = og_image.get('content', '')

    # Find the main content container
    container = None
    for selector in ['article', 'main', '.post-content', '.article-content',
                     '.entry-content', '[role="main"]']:
        container = soup.select_one(selector)
        if container:
            break
    if not container:
        container = soup.body

    if container:
        # Fallback image: extract first <img> from content if og:image is missing
        if not image_url:
            first_img = container.find('img')
            if first_img:
                image_url = first_img.get('src') or first_img.get('data-src') or ''

        _preprocess_figures(container)
        body_html = str(container)
    else:
        body_html = ''

    body_md = md(body_html, heading_style='ATX',
                 strip=['nav', 'header', 'footer', 'aside', 'figure', 'figcaption'])

    # Strip the thumbnail image from body to avoid duplication with frontmatter
    if image_url:
        body_md = _strip_thumbnail_from_body(body_md, image_url)

    # Clean CTA/navigation patterns
    for pattern in _CTA_PATTERNS:
        body_md = re.sub(pattern, '', body_md, flags=re.IGNORECASE)

    body_md = _clean_markdown(body_md)
    body_md = _enforce_h2_only(body_md)
    body_md = _strip_title_heading(body_md, title)

    # JSON-LD fallback: if HTML extraction yielded little content,
    # try extracting structured data from JSON-LD script blocks.
    # This handles JS-heavy pages (Humanitix, SPAs) that embed
    # Schema.org data server-side even when the UI needs JS to render.
    if len(body_md) < 100:
        ld_data = _extract_json_ld(soup)
        if ld_data:
            logger.info('scrape_general: HTML body too short (%d chars), using JSON-LD fallback', len(body_md))
            if not title and ld_data.get('title'):
                title = ld_data['title']
            if not author and ld_data.get('author'):
                author = ld_data['author']
            if not pub_date and ld_data.get('date'):
                pub_date = ld_data['date']
            if not image_url and ld_data.get('image_url'):
                image_url = ld_data['image_url']
            if ld_data.get('body_markdown'):
                body_md = ld_data['body_markdown']

    return {
        'title': title,
        'author': author,
        'date': pub_date,
        'image_url': image_url,
        'body_markdown': body_md,
        'source_url': url,
    }


def scrape_url(url):
    """
    Scrape a URL, routing to the appropriate scraper.
    Returns structured data dict.
    """
    if _SUBSTACK_RE.match(url):
        return scrape_substack(url)
    return scrape_general_url(url)
