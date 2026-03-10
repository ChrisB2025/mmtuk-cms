"""Template integrity tests — verify templates load, includes exist, and
response HTML doesn't contain unresolved template variables."""

import re
from pathlib import Path

import pytest
from django.template import engines
from django.test import Client

pytestmark = pytest.mark.django_db

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'templates' / 'content'


class TestTemplateFilesExist:
    """Verify all {% include %} references point to existing template files."""

    INCLUDE_RE = re.compile(r'{%\s*include\s+["\']([^"\']+)["\']\s*%}')

    def _find_includes(self, template_path):
        """Extract all {% include "..." %} references from a template."""
        content = template_path.read_text(encoding='utf-8')
        return self.INCLUDE_RE.findall(content)

    def test_all_includes_resolve(self):
        """Every {% include %} target must exist as a template."""
        django_engine = engines['django']
        missing = []
        for template_file in TEMPLATE_DIR.rglob('*.html'):
            includes = self._find_includes(template_file)
            for include_path in includes:
                try:
                    django_engine.get_template(include_path)
                except Exception:
                    rel = template_file.relative_to(TEMPLATE_DIR)
                    missing.append(f'{rel} includes "{include_path}"')
        assert not missing, f'Missing template includes:\n' + '\n'.join(missing)


class TestBaseTemplate:
    """Verify the base template loads and has required blocks."""

    def test_base_template_loads(self):
        django_engine = engines['django']
        template = django_engine.get_template('content/base.html')
        assert template is not None

    def test_base_has_required_blocks(self):
        content = (TEMPLATE_DIR / 'base.html').read_text(encoding='utf-8')
        for block in ('title', 'content'):
            assert f'{{% block {block} %}}' in content, f'base.html missing block "{block}"'


class TestRenderedHTMLQuality:
    """Check that rendered pages don't leak unresolved template variables."""

    UNRESOLVED_VAR_RE = re.compile(r'\{\{[^}]*\}\}')

    @pytest.mark.parametrize('url', [
        '/',
        '/research/',
        '/education/',
        '/community/',
        '/about-us/',
        '/donate/',
        '/join/',
        '/founders/',
        '/privacy-policy/',
        '/terms-of-engagement/',
        '/cookie-preferences/',
    ])
    def test_no_unresolved_template_vars(self, client, url):
        """Rendered HTML should not contain {{ variable }} markers."""
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode()
        # Filter out JavaScript template literals and JSON-LD
        # Only check the main HTML body, not script tags
        html_no_scripts = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        matches = self.UNRESOLVED_VAR_RE.findall(html_no_scripts)
        # Filter out intentional JS template syntax (e.g., in inline styles)
        real_leaks = [m for m in matches if '{{' in m and 'style' not in m.lower()]
        assert not real_leaks, f'{url} has unresolved template vars: {real_leaks}'

    def test_meta_tags_present(self, client):
        """Homepage should have title and meta description."""
        response = client.get('/')
        html = response.content.decode()
        assert '<title>' in html
        assert 'meta name="description"' in html or 'meta property="og:description"' in html


class TestErrorTemplates:
    """Verify error pages render."""

    def test_404_template_exists(self):
        assert (TEMPLATE_DIR / '404.html').exists()

    def test_401_template_exists(self):
        assert (TEMPLATE_DIR / '401.html').exists()
