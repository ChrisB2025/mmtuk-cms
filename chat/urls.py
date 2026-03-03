from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('', views.index, name='index'),
    path('new/', views.new_conversation, name='new_conversation'),
    path('c/<uuid:conversation_id>/', views.conversation, name='conversation'),
    path('c/<uuid:conversation_id>/send/', views.send_message, name='send_message'),
    path('c/<uuid:conversation_id>/upload-pdf/', views.upload_pdf, name='upload_pdf'),
    path('c/<uuid:conversation_id>/discard/', views.discard_conversation, name='discard_conversation'),
    path('c/<uuid:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('pending/', views.pending_list, name='pending_list'),
    path('pending/<uuid:draft_id>/', views.pending_detail, name='pending_detail'),
    path('pending/<uuid:draft_id>/approve/', views.approve_draft, name='approve_draft'),
    path('pending/<uuid:draft_id>/reject/', views.reject_draft, name='reject_draft'),
    # Content browser
    path('content/', views.content_browser, name='content_browser'),
    path('content/health/', views.content_health, name='content_health'),
    path('content/<str:content_type>/<str:slug>/', views.content_detail, name='content_detail'),
    path('content/<str:content_type>/<str:slug>/edit/', views.edit_in_chat, name='edit_in_chat'),
    path('content/<str:content_type>/<str:slug>/quick-edit/', views.quick_edit, name='quick_edit'),
    path('content/<str:content_type>/<str:slug>/delete/', views.delete_content, name='delete_content'),
    path('content/<str:content_type>/<str:slug>/toggle-featured/', views.toggle_featured, name='toggle_featured'),
    # Event archive
    path('events/archive/', views.event_archive, name='event_archive'),
    path('content/<str:content_type>/<str:slug>/unarchive/', views.unarchive_event, name='unarchive_event'),
    # Media library
    path('media/', views.media_library, name='media_library'),
    path('repo-images/<path:image_path>', views.repo_image, name='repo_image'),
    # APIs
    path('api/content/', views.content_api, name='content_api'),
    path('api/upload-image/', views.upload_image, name='upload_image'),
    path('api/delete-image/', views.delete_image, name='delete_image'),
    path('api/images/', views.images_api, name='images_api'),
    path('api/content/bulk/', views.bulk_action, name='bulk_action'),
    path('api/pending-publish/', views.pending_publish, name='pending_publish'),
    # Review & Publish
    path('review/', views.review_changes, name='review_changes'),
    path('review/discard/', views.discard_unpublished, name='discard_unpublished'),
    path('publish/', views.publish_changes, name='publish_changes'),
    # Redirect Management (SEO)
    path('redirects/', views.redirect_management, name='redirect_management'),
    path('redirects/edit/', views.edit_redirect, name='edit_redirect'),
    path('redirects/remove/', views.remove_redirect, name='remove_redirect'),
    # Page management
    path('pages/', views.page_manager, name='page_manager'),
    path('pages/<str:page_key>/', views.page_editor, name='page_editor'),
    path('pages/<str:page_key>/section/<str:section_key>/', views.page_section_editor, name='page_section_editor'),
    path('api/pages/<str:page_key>/section/<str:section_key>/', views.page_section_api, name='page_section_api'),
    # Site config (admin-only)
    path('site-config/', views.site_config_editor, name='site_config_editor'),
    path('api/site-config/', views.site_config_api, name='site_config_api'),
]
