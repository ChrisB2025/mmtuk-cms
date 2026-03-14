from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'website'

_LEGACY_ARTICLE_REDIRECTS = {
    'mmt-uk-commentary-1': 'mmtuk-commentary-1',
    'mmt-uk-commentary-10': 'mmtuk-commentary-10',
    'mmt-uk-commentary-10-1940b': 'mmtuk-commentary-10-1940b',
    'mmt-uk-commentary-1-1c57f': 'mmtuk-commentary-1-1c57f',
    'mmt-uk-commentary-13': 'mmtuk-commentary-13',
    'mmt-uk-commentary-16': 'mmtuk-commentary-16',
    'mmt-uk-commentary-19': 'mmtuk-commentary-19',
    'mmt-uk-commentary-4': 'mmtuk-commentary-4',
    'mmt-uk-commentary-4-15f37': 'mmtuk-commentary-4-15f37',
    'mmt-uk-commentary-7': 'mmtuk-commentary-7',
    'mmt-uk-commentary-7-02474': 'mmtuk-commentary-7-02474',
    'mmt-uk-feature-article-11': 'mmtuk-feature-article-11',
    'mmt-uk-feature-article-14': 'mmtuk-feature-article-14',
    'mmt-uk-feature-article-17': 'mmtuk-feature-article-17',
    'mmt-uk-feature-article-2': 'mmtuk-feature-article-2',
    'mmt-uk-feature-article-20': 'mmtuk-feature-article-20',
    'mmt-uk-feature-article-2-7a1db': 'mmtuk-feature-article-2-7a1db',
    'mmt-uk-feature-article-5': 'mmtuk-feature-article-5',
    'mmt-uk-feature-article-5-4310b': 'mmtuk-feature-article-5-4310b',
    'mmt-uk-feature-article-8': 'mmtuk-feature-article-8',
    'mmt-uk-feature-article-8-30444': 'mmtuk-feature-article-8-30444',
    'mmt-uk-research-12': 'mmtuk-research-12',
    'mmt-uk-research-15': 'mmtuk-research-15',
    'mmt-uk-research-18': 'mmtuk-research-18',
    'mmt-uk-research-3': 'mmtuk-research-3',
    'mmt-uk-research-3-c35d1': 'mmtuk-research-3-c35d1',
    'mmt-uk-research-6': 'mmtuk-research-6',
    'mmt-uk-research-6-72f4d': 'mmtuk-research-6-72f4d',
    'mmt-uk-research-9': 'mmtuk-research-9',
    'mmt-uk-research-9-3603a': 'mmtuk-research-9-3603a',
}

urlpatterns = [
    # Legacy mmt-uk-* article slug redirects (SEO preservation from Astro migration)
    *[path(f'articles/{old}/', RedirectView.as_view(url=f'/articles/{new}/', permanent=True))
      for old, new in _LEGACY_ARTICLE_REDIRECTS.items()],
    # Legacy ecosystem redirect
    path('ecosystem/mmt-uk-discord/', RedirectView.as_view(url='/ecosystem/mmtuk-discord/', permanent=True)),
    # Deleted briefing redirect (SEO preservation)
    path('briefings/shadows-on-the-wall-the-monetary-myths-that-shape-british-politics-vincent-gomez/',
         RedirectView.as_view(url='/research/briefings/', permanent=True)),

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
