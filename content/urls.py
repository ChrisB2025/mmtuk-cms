from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('research/briefings/<slug:slug>/', views.briefing_detail, name='briefing_detail'),
    path('research/briefings/', views.briefings_index, name='briefings_index'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('research/', views.research, name='research'),
    path('about-us/', views.about_us, name='about_us'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-engagement/', views.terms_of_engagement, name='terms_of_engagement'),
    path('cookie-preferences/', views.cookie_preferences, name='cookie_preferences'),
    path('', views.homepage, name='homepage'),
]
