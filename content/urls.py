from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'website'

urlpatterns = [
    path('research/briefings/<slug:slug>/', views.briefing_detail, name='briefing_detail'),
    path('research/briefings/', views.briefings_index, name='briefings_index'),
    path('articles/', views.articles_index, name='articles_index'),
    path('articles/<slug:slug>/', views.article_detail, name='article_detail'),
    path('education/articles/<slug:slug>/', views.article_detail, name='education_article_detail'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('research/', views.research, name='research'),
    path('research/job-guarantee/', views.job_guarantee, name='job_guarantee'),
    path('education/', views.education, name='education'),
    path('community/', views.community, name='community'),
    path('founders/launch-event/', views.founders_launch_event, name='founders_launch_event'),
    path('founders/', views.founders, name='founders'),
    path('job-guarantee/', RedirectView.as_view(url='/research/job-guarantee/', permanent=True)),
    path('library/', RedirectView.as_view(url='/education/', permanent=True)),
    path('ecosystem/<slug:slug>/', RedirectView.as_view(url='/', permanent=True)),
    path('ecosystem/', RedirectView.as_view(url='/', permanent=True)),
    path('local-group/<slug:group_slug>/<slug:news_slug>/', views.local_news_detail, name='local_news_detail'),
    path('local-group/<slug:slug>/', views.local_group_detail, name='local_group_detail'),
    path('about-us/', views.about_us, name='about_us'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-engagement/', views.terms_of_engagement, name='terms_of_engagement'),
    path('cookie-preferences/', views.cookie_preferences, name='cookie_preferences'),
    path('donate/', views.donate, name='donate'),
    path('join/', views.join, name='join'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('', views.homepage, name='homepage'),
]
