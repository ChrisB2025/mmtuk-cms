from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('cms/', include('chat.urls')),
    path('', include('content.urls')),
]

handler404 = 'content.views.custom_404'
handler403 = 'content.views.custom_401'
