from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-engagement/', views.terms_of_engagement, name='terms_of_engagement'),
    path('cookie-preferences/', views.cookie_preferences, name='cookie_preferences'),
    path('', views.homepage, name='homepage'),
]
