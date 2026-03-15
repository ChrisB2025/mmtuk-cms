from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from content.models import Article, Briefing, LocalGroup, LocalNews, News


class ArticleSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Article.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated_at


class BriefingSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Briefing.objects.filter(status='published', draft=False)

    def lastmod(self, obj):
        return obj.updated_at


class NewsSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return News.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated_at


class LocalGroupSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return LocalGroup.objects.filter(status='published', active=True)

    def lastmod(self, obj):
        return obj.updated_at


class LocalNewsSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return LocalNews.objects.filter(status='published')

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.3

    _static_pages = [
        'website:homepage',
        'website:research',
        'website:education',
        'website:briefings_index',
        'website:community',
        'website:about_us',
        'website:donate',
        'website:join',
        'website:job_guarantee',
    ]

    def items(self):
        return self._static_pages

    def location(self, item):
        return reverse(item)
