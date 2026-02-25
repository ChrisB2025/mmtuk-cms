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


def _fetch_html(url):
    """Fetch a URL and return the HTML content."""
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
