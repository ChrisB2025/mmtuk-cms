"""
URL scraping for importing content (Substack articles, general URLs).
"""

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
    resp = httpx.get(
        url,
        headers={'User-Agent': _USER_AGENT},
        follow_redirects=True,
        timeout=30,
    )
    resp.raise_for_status()
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
    Convert any h3 (###) headings to h2 (##).
    Briefings should only use h2 — h3 renders larger than h2 in Webflow CSS.
    """
    return re.sub(r'^###\s+', '## ', text, flags=re.MULTILINE)


def scrape_substack(url):
    """
    Scrape a Substack article and return structured data.
    Returns a dict with title, author, date, publication, image_url, body_markdown, source_url.
    """
    html = _fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

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

    pub_date = ''
    meta_date = soup.find('meta', property='article:published_time')
    if meta_date:
        pub_date = meta_date.get('content', '')[:10]  # YYYY-MM-DD

    publication = ''
    og_site = soup.find('meta', property='og:site_name')
    if og_site:
        publication = og_site.get('content', '')

    image_url = ''
    og_image = soup.find('meta', property='og:image')
    if og_image:
        image_url = og_image.get('content', '')

    # Extract article body
    body_html = ''
    # Substack uses .body.markup or .available-content
    for selector in ['.body.markup', '.available-content', 'article', '.post-content']:
        container = soup.select_one(selector)
        if container:
            body_html = str(container)
            break

    if not body_html:
        # Fallback: find the largest text block
        main = soup.find('main') or soup.find('article') or soup.body
        if main:
            body_html = str(main)

    # Convert HTML to markdown
    body_md = md(body_html, heading_style='ATX', strip=['img', 'figure', 'figcaption'])

    # Clean up: remove subscription CTAs, share buttons
    cta_patterns = [
        r'Subscribe\s*\n',
        r'Share\s*\n',
        r'Thanks for reading.*?\n',
        r'Get more from.*?\n',
        r'\[Subscribe now\].*?\n',
        r'\[Share\].*?\n',
        r'A publication of.*?\n',
    ]
    for pattern in cta_patterns:
        body_md = re.sub(pattern, '', body_md, flags=re.IGNORECASE)

    body_md = _clean_markdown(body_md)
    body_md = _enforce_h2_only(body_md)

    return {
        'title': title,
        'author': author,
        'date': pub_date,
        'publication': publication,
        'image_url': image_url,
        'body_markdown': body_md,
        'source_url': url,
    }


def scrape_general_url(url):
    """
    Scrape a general URL for content import.
    Returns a dict with title, author, date, body_markdown, source_url.
    """
    html = _fetch_html(url)
    soup = BeautifulSoup(html, 'html.parser')

    title = ''
    og_title = soup.find('meta', property='og:title')
    if og_title:
        title = og_title.get('content', '')
    if not title:
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

    author = ''
    meta_author = soup.find('meta', attrs={'name': 'author'})
    if meta_author:
        author = meta_author.get('content', '')

    pub_date = ''
    meta_date = soup.find('meta', property='article:published_time')
    if meta_date:
        pub_date = meta_date.get('content', '')[:10]

    image_url = ''
    og_image = soup.find('meta', property='og:image')
    if og_image:
        image_url = og_image.get('content', '')

    # Find the main content
    body_html = ''
    for selector in ['article', 'main', '.post-content', '.article-content', '.entry-content', '[role="main"]']:
        container = soup.select_one(selector)
        if container:
            body_html = str(container)
            break

    if not body_html and soup.body:
        body_html = str(soup.body)

    body_md = md(body_html, heading_style='ATX', strip=['nav', 'header', 'footer', 'aside'])
    body_md = _clean_markdown(body_md)

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
