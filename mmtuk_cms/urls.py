from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cms/', include('chat.urls')),
    path('', include('content.urls')),
]

# Serve media files (CMS-uploaded images)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'content.views.custom_404'
handler403 = 'content.views.custom_401'
