from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.contrib.sites.requests import RequestSite
from django.urls import path, include, re_path
from django.views.static import serve

from content.sitemaps import (
    ArticleSitemap,
    BriefingSitemap,
    LocalGroupSitemap,
    LocalNewsSitemap,
    NewsSitemap,
    StaticSitemap,
)

sitemaps = {
    'articles': ArticleSitemap,
    'briefings': BriefingSitemap,
    'news': NewsSitemap,
    'local_groups': LocalGroupSitemap,
    'local_news': LocalNewsSitemap,
    'static': StaticSitemap,
}


def sitemap_view(request):
    return sitemap(request, sitemaps=sitemaps, site=RequestSite(request))


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cms/', include('chat.urls')),
    path('sitemap.xml', sitemap_view, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('content.urls')),
    # Serve media files in all environments (volume-persisted images)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

handler404 = 'content.views.custom_404'
handler403 = 'content.views.custom_401'
