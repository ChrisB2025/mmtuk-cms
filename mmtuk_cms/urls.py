from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cms/', include('chat.urls')),
    path('', include('content.urls')),
    # Serve media files in all environments (volume-persisted images)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

handler404 = 'content.views.custom_404'
handler403 = 'content.views.custom_401'
