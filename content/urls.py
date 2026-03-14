from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'website'

def _education_redirect(request, slug):
    """Redirect /articles/<slug>/ and /education/articles/<slug>/ to /education/<slug>/."""
    from django.shortcuts import redirect
    return redirect(f'/education/{slug}/', permanent=True)


urlpatterns = [
    # Legacy ecosystem redirect
    path('ecosystem/mmt-uk-discord/', RedirectView.as_view(url='/ecosystem/mmtuk-discord/', permanent=True)),
    # Deleted briefing redirect (SEO preservation)
    path('briefings/shadows-on-the-wall-the-monetary-myths-that-shape-british-politics-vincent-gomez/',
         RedirectView.as_view(url='/research/briefings/', permanent=True)),

    path('research/briefings/<slug:slug>/', views.briefing_detail, name='briefing_detail'),
    path('research/briefings/', views.briefings_index, name='briefings_index'),
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('research/', views.research, name='research'),
    path('research/job-guarantee/', views.job_guarantee, name='job_guarantee'),
    path('education/', views.education, name='education'),
    # Education articles — canonical URL (after /education/ to avoid slug capture)
    path('education/<slug:slug>/', views.article_detail, name='education_article_detail'),
    # Legacy article URL redirects (SEO preservation)
    path('articles/<slug:slug>/', _education_redirect),
    path('education/articles/<slug:slug>/', _education_redirect),
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
