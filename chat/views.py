"""
Chat views: conversation UI, message handling, pending approvals.
"""

import json
import logging
import re
import time
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.http import FileResponse, Http404, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from .models import Conversation, Message, ContentDraft, ContentAuditLog
from .services.anthropic_service import (
    build_system_prompt,
    get_conversation_messages,
    call_claude,
    extract_action_block,
    strip_action_block,
)
from .services.content_service import (
    create_content, update_content, delete_content as delete_content_orm,
    get_image_save_path, estimate_read_time,
)
from .services.content_reader_service import (
    check_slug_exists, list_content, read_content,
    search_content, get_content_stats, list_images,
)
from .services.field_mapping import (
    get_model_class, get_title_field, get_title,
    instance_to_frontmatter, generate_slug, MODEL_MAP,
)
from .services.image_catalog import categorise_images, _group_responsive_variants
from .services.scraper_service import scrape_url
from .services.image_service import process_image
from .services.pdf_service import extract_pdf, save_pdf_images, get_pdf_image
from .services.docx_service import extract_docx

logger = logging.getLogger(__name__)

# --- Suggested actions for empty conversations ---

SUGGESTED_ACTIONS = [
    {
        'id': 'add_briefing',
        'label': 'Add Briefing',
        'message': 'I want to add a briefing to the MMTUK site.',
        'action_type': 'send',
        'content_type': 'briefing',
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_news',
        'label': 'Add News',
        'message': 'I want to add a news item for the MMTUK site.',
        'action_type': 'send',
        'content_type': 'news',
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_article',
        'label': 'Write Article',
        'message': 'I want to write a new article for the MMTUK site.',
        'action_type': 'send',
        'content_type': 'article',
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_local_event',
        'label': 'Add Local Event',
        'message': 'I want to add a local event for {local_group}.',
        'action_type': 'send',
        'content_type': 'local_event',
        'admin_only': False,
        'needs_group': True,
    },
    {
        'id': 'add_local_news',
        'label': 'Add Local News',
        'message': 'I want to add local news for {local_group}.',
        'action_type': 'send',
        'content_type': 'local_news',
        'admin_only': False,
        'needs_group': True,
    },
    {
        'id': 'upload_document',
        'label': 'Upload Document',
        'message': '',
        'action_type': 'upload',
        'content_type': None,
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_bio',
        'label': 'Add Team Member',
        'message': 'I want to add a new team member bio.',
        'action_type': 'send',
        'content_type': 'bio',
        'admin_only': True,
        'needs_group': False,
    },
    {
        'id': 'add_ecosystem',
        'label': 'Add Ecosystem Entry',
        'message': 'I want to add a new ecosystem entry.',
        'action_type': 'send',
        'content_type': 'ecosystem',
        'admin_only': False,
        'needs_group': False,
    },
]


def _get_suggested_actions(profile):
    """Filter SUGGESTED_ACTIONS by the user's permissions. Returns a list of dicts."""
    actions = []
    group_name = dict(profile._meta.get_field('local_group').choices).get(profile.local_group, '')

    for action in SUGGESTED_ACTIONS:
        # "Upload a PDF" is available to everyone
        if action['content_type'] is None:
            actions.append({
                'label': action['label'],
                'message': action['message'],
                'action_type': action['action_type'],
            })
            continue

        # Admin-only actions
        if action['admin_only'] and profile.role != 'admin':
            continue

        # Permission check
        if not profile.can_create(action['content_type']):
            continue

        # Group-specific actions need a local_group
        if action['needs_group']:
            if profile.role in ('admin', 'editor'):
                # Admins/editors see a generic version
                msg = action['message'].replace('{local_group}', 'a local group')
            elif profile.local_group:
                msg = action['message'].replace('{local_group}', group_name or profile.local_group)
            else:
                continue  # No group assigned, skip
        else:
            msg = action['message']

        actions.append({
            'label': action['label'],
            'message': msg,
            'action_type': action['action_type'],
        })

    return actions


def health(request):
    """Health check endpoint for Railway."""
    return JsonResponse({'status': 'ok'})


@login_required
def index(request):
    """Main chat page — shows the most recent conversation or creates one."""
    conversations = Conversation.objects.filter(user=request.user)[:20]
    profile = request.user.profile

    # Check for pending draft notifications
    notifications = []
    recent_decisions = ContentDraft.objects.filter(
        created_by=request.user,
        status__in=['approved', 'rejected'],
        reviewed_at__isnull=False,
    ).order_by('-reviewed_at')[:5]
    for draft in recent_decisions:
        if draft.status == 'approved':
            notifications.append(f'Your {draft.content_type} "{draft.title}" has been approved and published!')
        elif draft.status == 'rejected':
            feedback = f' Feedback: {draft.review_feedback}' if draft.review_feedback else ''
            notifications.append(f'Your {draft.content_type} "{draft.title}" was not approved.{feedback}')

    return render(request, 'chat/index.html', {
        'conversations': conversations,
        'current_conversation': None,
        'messages': [],
        'profile': profile,
        'notifications': notifications,
    })


@login_required
@never_cache
def conversation(request, conversation_id):
    """View a specific conversation."""
    conv = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    conversations = Conversation.objects.filter(user=request.user)[:20]
    # Exclude internal/injected messages — kept in DB for Claude context but not shown in UI.
    # [SYSTEM:  — injected document text (huge, confusing as a user bubble)
    # [Uploaded — upload marker placeholder
    # content='' — empty assistant messages (stripped action-only responses)
    messages = (
        conv.messages
        .exclude(content__startswith='[SYSTEM:')
        .exclude(content__startswith='[Uploaded')
        .exclude(content='')
        .exclude(content__regex=r'^\s+$')
    )
    profile = request.user.profile

    # Show suggested actions for empty conversations
    suggested_actions = []
    if not conv.messages.exists():
        suggested_actions = _get_suggested_actions(profile)

    # Check if conversation has pending drafts (for showing discard button)
    has_pending_drafts = ContentDraft.objects.filter(
        conversation=conv,
        status='pending'
    ).exists()

    return render(request, 'chat/index.html', {
        'conversations': conversations,
        'current_conversation': conv,
        'messages': messages,
        'profile': profile,
        'notifications': [],
        'suggested_actions': suggested_actions,
        'has_pending_drafts': has_pending_drafts,
    })


@login_required
def new_conversation(request):
    """Create a new conversation and redirect to it."""
    conv = Conversation.objects.create(user=request.user)
    return redirect('conversation', conversation_id=conv.id)


def _check_rate_limit(user):
    """Check if user has exceeded the message rate limit. Returns True if OK."""
    cache_key = f'chat_rate_{user.id}'
    count = cache.get(cache_key, 0)
    if count >= settings.CHAT_RATE_LIMIT:
        return False
    cache.set(cache_key, count + 1, timeout=3600)
    return True


def _handle_scrape_action(action_data, profile, conv):
    """
    Handle a scrape action: fetch URL content, inject it into the conversation,
    and return a formatted preview. Claude will see the scraped data in the
    conversation history on the user's next message.
    """
    url = action_data.get('url', '')
    if not url:
        return 'I tried to scrape a URL but none was provided. Could you paste the URL again?'

    try:
        scraped = scrape_url(url)
    except Exception:
        logger.exception('Scrape failed for %s', url)
        return 'I wasn\'t able to fetch content from that URL. Could you check it\'s correct and try again?'

    # Build a message with the scraped data for Claude to see on next call
    scraped_summary = (
        f'[SYSTEM: The URL {url} was scraped. Here is the extracted data]\n\n'
        f'Title: {scraped.get("title", "")}\n'
        f'Author: {scraped.get("author", "")}\n'
        f'Date: {scraped.get("date", "")}\n'
        f'Publication: {scraped.get("publication", "")}\n'
        f'Image URL: {scraped.get("image_url", "")}\n\n'
        f'Article body (markdown):\n\n{scraped.get("body_markdown", "")[:8000]}'
    )

    # Save the scraped data as a system-injected user message
    Message.objects.create(conversation=conv, role='user', content=scraped_summary)

    # Return formatted preview directly (no second Claude call — halves request time)
    title = scraped.get('title', 'Untitled')
    author = scraped.get('author', '')
    date = scraped.get('date', '')
    pub = scraped.get('publication', '')
    body_preview = scraped.get('body_markdown', '')[:500]

    parts = ["I've imported the article from that URL. Here's what I found:\n"]
    parts.append(f'**Title:** {title}')
    if author:
        parts.append(f'**Author:** {author}')
    if date:
        parts.append(f'**Date:** {date}')
    if pub:
        parts.append(f'**Publication:** {pub}')
    if body_preview:
        parts.append(f'\n**Preview:**\n{body_preview}...')
    parts.append('\nWould you like me to create this as an article on the MMTUK site? '
                 'I can adjust the title, category, or content before publishing.')

    return '\n'.join(parts)


def _handle_content_action(action_data, profile, conv, user):
    """
    Handle a create action: validate, save to DB, handle images,
    and either publish directly or save as draft.
    Returns (response_text, action_result_dict).
    """
    content_type = action_data.get('content_type', '')
    frontmatter = action_data.get('frontmatter', {})
    body = action_data.get('body', '')
    images = action_data.get('images', [])
    slug = frontmatter.get('slug', '')
    title = frontmatter.get('title') or frontmatter.get('heading') or frontmatter.get('name', 'Untitled')

    # Check for duplicate slug
    if check_slug_exists(content_type, slug):
        return (
            f'A {content_type} with the slug "{slug}" already exists. '
            f'Please choose a different slug or ask to edit the existing content instead.',
            {'type': 'error', 'message': f'Duplicate slug: {slug}'},
        )

    # Check permissions
    local_group = frontmatter.get('localGroup', '')
    if not profile.can_create(content_type, local_group):
        return (
            f'Sorry, your role ({profile.get_role_display()}) doesn\'t have permission to create {content_type} content.',
            {'type': 'error', 'message': 'Permission denied'},
        )

    # Process images
    image_bytes = None
    image_save_path = None
    image_web_path = None
    if images:
        img_info = images[0]

        if img_info.get('source') == 'pdf':
            # Image from a previously uploaded PDF
            pdf_index = img_info.get('index', 0)
            pdf_bytes, pdf_ext = get_pdf_image(conv.id, pdf_index)
            if pdf_bytes:
                image_bytes = pdf_bytes
                save_as = img_info.get('save_as', '')
                if save_as:
                    ext = save_as.rsplit('.', 1)[-1] if '.' in save_as else 'webp'
                    image_save_path, image_web_path = get_image_save_path(content_type, slug, ext)
                else:
                    image_save_path, image_web_path = get_image_save_path(content_type, slug)
        else:
            # Image from URL
            img_url = img_info.get('url', '')
            if img_url:
                t1 = time.monotonic()
                img_bytes, img_filename = process_image(img_url, slug)
                logger.info('content_action timing: image_download=%.1fs', time.monotonic() - t1)
                if img_bytes:
                    image_bytes = img_bytes
                    image_save_path, image_web_path = get_image_save_path(content_type, slug)
                else:
                    logger.warning('content_action: process_image returned None for url=%.80s', img_url)

    # Check if user can publish directly
    can_publish = profile.can_publish_directly(content_type, local_group)

    if can_publish:
        # Direct publish to database
        try:
            status = 'published'
            instance, errors = create_content(content_type, frontmatter, body, status)
            if errors:
                error_msg = 'There were validation errors:\n' + '\n'.join(f'- {e}' for e in errors)
                return error_msg, {'type': 'error', 'message': error_msg}

            # Save image to filesystem and update model's image field
            if image_bytes and image_save_path:
                image_save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(image_save_path, 'wb') as f:
                    f.write(image_bytes)
                # Update the image field on the model if applicable
                if image_web_path:
                    _update_image_field(instance, content_type, image_web_path)

            # Save as published draft for record keeping
            ContentDraft.objects.create(
                conversation=conv,
                created_by=user,
                content_type=content_type,
                title=title,
                slug=slug,
                frontmatter_json=frontmatter,
                body_markdown=body,
                status='published',
                git_commit_sha='',
            )

            _log_audit(content_type, slug, 'create', user, '')

            return (
                f'Content published successfully! **{title}** is now live.',
                {'type': 'content_created', 'title': title, 'content_type': content_type},
            )

        except Exception:
            logger.exception('Failed to publish content')
            # Save as pending draft so nothing is lost
            draft = ContentDraft.objects.create(
                conversation=conv,
                created_by=user,
                content_type=content_type,
                title=title,
                slug=slug,
                frontmatter_json=frontmatter,
                body_markdown=body,
                image_data=image_bytes,
                image_path=str(image_save_path) if image_save_path else '',
                status='pending',
            )
            return (
                f'There was an error publishing the content, but I\'ve saved it as a draft (#{draft.id}). '
                f'An admin can review and publish it from the Pending dashboard.',
                {'type': 'draft_pending', 'draft_id': str(draft.id)},
            )
    else:
        # Save as draft for approval
        draft = ContentDraft.objects.create(
            conversation=conv,
            created_by=user,
            content_type=content_type,
            title=title,
            slug=slug,
            frontmatter_json=frontmatter,
            body_markdown=body,
            image_data=image_bytes,
            image_path=str(image_save_path) if image_save_path else '',
            status='pending',
        )
        return (
            f'Your {content_type} "{title}" has been saved as a draft and is awaiting approval from an editor or admin.',
            {'type': 'draft_pending', 'draft_id': str(draft.id)},
        )


def _ensure_event_image(instance):
    """
    For a LocalEvent, fetch the og:image from the event link and save it to
    MEDIA_ROOT/images/ (persistent volume). Skips if a valid file already exists.
    """
    from pathlib import Path
    from .services.scraper_service import scrape_general_url
    from .services.image_service import process_image

    link = getattr(instance, 'link', '')
    if not link:
        return

    # Check if image is already saved to the persistent media volume
    image = getattr(instance, 'image', '')
    if image and image.startswith('/media/images/'):
        media_path = Path(settings.MEDIA_ROOT) / 'images' / Path(image).name
        if media_path.exists():
            return  # Already saved to persistent volume

    try:
        data = scrape_general_url(link)
        image_url = data.get('image_url', '')
        if not image_url:
            logger.info('_ensure_event_image: no og:image found for %s', link)
            return
        img_bytes, _ = process_image(image_url, instance.slug)
        if not img_bytes:
            logger.warning('_ensure_event_image: image processing failed for %s', image_url)
            return
        # Save to persistent MEDIA_ROOT volume
        media_dir = Path(settings.MEDIA_ROOT) / 'images'
        media_dir.mkdir(parents=True, exist_ok=True)
        filename = f'{instance.slug}.webp'
        with open(media_dir / filename, 'wb') as f:
            f.write(img_bytes)
        web_path = f'/media/images/{filename}'
        instance.image = web_path
        instance.save(update_fields=['image'])
        logger.info('_ensure_event_image: saved %s for %s', web_path, instance.slug)
    except Exception:
        logger.exception('_ensure_event_image: failed for %s', link)


def _update_image_field(instance, content_type, web_path):
    """Update the appropriate image field on a model instance after saving an image."""
    field_name = None
    if content_type == 'briefing' and hasattr(instance, 'thumbnail'):
        instance.thumbnail = web_path
        field_name = 'thumbnail'
    elif content_type == 'bio' and hasattr(instance, 'photo'):
        instance.photo = web_path
        field_name = 'photo'
    elif hasattr(instance, 'thumbnail'):
        instance.thumbnail = web_path
        field_name = 'thumbnail'
    elif hasattr(instance, 'image'):
        instance.image = web_path
        field_name = 'image'
    if field_name:
        instance.save(update_fields=[field_name])


def _handle_read_action(action_data, profile, conv):
    """
    Handle a read action: load content from repo, inject into conversation,
    and return a formatted summary. Claude will see the loaded content in the
    conversation history on the user's next message.
    """
    content_type = action_data.get('content_type', '')
    slug = action_data.get('slug', '')

    if not content_type or not slug:
        return 'I need both a content type and slug to read content. Could you specify which item you want to view?'

    item = read_content(content_type, slug)
    if not item:
        return f'I couldn\'t find a {content_type} with slug "{slug}". Please check the slug and try again.'

    fm = item['frontmatter']
    title = fm.get('title') or fm.get('heading') or fm.get('name', 'Untitled')

    # Build a summary for the conversation (for Claude to see on next call)
    fm_lines = '\n'.join(f'  {k}: {v}' for k, v in fm.items())
    body_preview = item['body'][:6000]
    truncated = '' if len(item['body']) <= 6000 else '\n\n[Body truncated — full content is longer]'

    injected = (
        f'[SYSTEM: Loaded {content_type} "{title}" (slug: {slug})]\n\n'
        f'Frontmatter:\n{fm_lines}\n\n'
        f'Body:\n\n{body_preview}{truncated}'
    )

    Message.objects.create(conversation=conv, role='user', content=injected)

    # Return formatted summary directly (no second Claude call)
    display_body = item['body'][:500]
    fm_display = '\n'.join(f'- **{k}:** {v}' for k, v in fm.items() if v)

    parts = [f'Here\'s the {content_type} **"{title}"** (slug: `{slug}`):']
    if fm_display:
        parts.append(f'\n**Frontmatter:**\n{fm_display}')
    if display_body:
        parts.append(f'\n**Body preview:**\n{display_body}...')
    parts.append('\nWhat would you like to do with this content?')

    return '\n'.join(parts)


def _handle_edit_action(action_data, profile, conv, user):
    """
    Handle an edit action: update content in the database.
    Returns (response_text, action_result_dict).
    """
    content_type = action_data.get('content_type', '')
    slug = action_data.get('slug', '')
    new_frontmatter = action_data.get('frontmatter', {})
    new_body = action_data.get('body', None)  # None means keep existing
    images = action_data.get('images', [])

    if not content_type or not slug:
        return (
            'I need both a content type and slug to edit content.',
            {'type': 'error', 'message': 'Missing content type or slug'},
        )

    # Check permissions
    local_group = new_frontmatter.get('localGroup', '')
    if not profile.can_edit(content_type, local_group):
        return (
            f'Sorry, your role ({profile.get_role_display()}) doesn\'t have permission to edit {content_type} content.',
            {'type': 'error', 'message': 'Permission denied'},
        )

    # Process images if provided
    image_bytes = None
    image_save_path = None
    image_web_path = None
    if images:
        img_info = images[0]
        img_url = img_info.get('url', '')
        if img_url:
            img_bytes, img_filename = process_image(img_url, slug)
            if img_bytes:
                image_bytes = img_bytes
                image_save_path, image_web_path = get_image_save_path(content_type, slug)

    try:
        # Update content via ORM
        instance, errors = update_content(content_type, slug, new_frontmatter, new_body)
        if errors:
            error_msg = 'Validation errors:\n' + '\n'.join(f'- {e}' for e in errors)
            return error_msg, {'type': 'error', 'message': error_msg}

        title = get_title(content_type, instance)

        # Save image to filesystem and update model
        if image_bytes and image_save_path:
            image_save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(image_save_path, 'wb') as f:
                f.write(image_bytes)
            if image_web_path:
                _update_image_field(instance, content_type, image_web_path)

        # Merge frontmatter for the draft record
        existing = read_content(content_type, slug)
        merged_fm = existing['frontmatter'] if existing else new_frontmatter

        # Record the edit
        ContentDraft.objects.create(
            conversation=conv,
            created_by=user,
            content_type=content_type,
            title=title,
            slug=slug,
            frontmatter_json=merged_fm,
            body_markdown=new_body or (existing['body'] if existing else ''),
            status='published',
            git_commit_sha='',
        )

        # Log to audit trail
        _log_audit(content_type, slug, 'edit', user, '')

        return (
            f'Content updated successfully! **{title}** is now live.',
            {'type': 'content_edited', 'title': title, 'content_type': content_type},
        )

    except Exception:
        logger.exception('Failed to edit content')
        return (
            f'There was an error saving the edits. Please try again.',
            {'type': 'error', 'message': 'Failed to save edits'},
        )


def _handle_delete_action(action_data, profile, conv, user):
    """
    Handle a delete action: remove content from the database.
    Returns (response_text, action_result_dict).
    """
    content_type = action_data.get('content_type', '')
    slug = action_data.get('slug', '')

    if not content_type or not slug:
        return (
            'I need both a content type and slug to delete content.',
            {'type': 'error', 'message': 'Missing content type or slug'},
        )

    # Check permissions
    if not profile.can_delete(content_type):
        return (
            f'Sorry, your role ({profile.get_role_display()}) doesn\'t have permission to delete content.',
            {'type': 'error', 'message': 'Permission denied'},
        )

    # Verify content exists and get title before deleting
    existing = read_content(content_type, slug)
    if not existing:
        return (
            f'Could not find {content_type} with slug "{slug}" to delete.',
            {'type': 'error', 'message': 'Content not found'},
        )

    title = (
        existing['frontmatter'].get('title')
        or existing['frontmatter'].get('heading')
        or existing['frontmatter'].get('name')
        or 'Untitled'
    )

    try:
        success, error = delete_content_orm(content_type, slug)
        if not success:
            return (
                f'Failed to delete "{title}": {error}',
                {'type': 'error', 'message': error},
            )

        # Log to audit trail
        _log_audit(content_type, slug, 'delete', user, '')

        return (
            f'**{title}** ({content_type}) has been deleted.',
            {'type': 'content_deleted', 'title': title, 'content_type': content_type},
        )

    except Exception:
        logger.exception('Failed to delete content')
        return (
            f'There was an error deleting "{title}". Please try again.',
            {'type': 'error', 'message': 'Failed to delete'},
        )


def _handle_list_action(action_data, profile, conv):
    """
    Handle a list action: list content, inject into conversation, and return
    a formatted list. Claude will see the full data on the user's next message.
    """
    content_type = action_data.get('content_type', None)
    sort_by = action_data.get('sort', 'date_desc')
    limit = action_data.get('limit', 10)

    items = list_content(content_type)

    # Sort
    if sort_by == 'date_asc':
        items = sorted(items, key=lambda x: _sort_date(x))
    elif sort_by == 'title_asc':
        items = sorted(items, key=lambda x: x.get('title', '').lower())
    elif sort_by == 'title_desc':
        items = sorted(items, key=lambda x: x.get('title', '').lower(), reverse=True)
    else:
        items = sorted(items, key=lambda x: _sort_date(x), reverse=True)

    items = items[:limit]

    if not items:
        type_label = content_type or 'any type'
        injected = f'[SYSTEM: No content found of type "{type_label}"]'
    else:
        lines = [f'[SYSTEM: Found {len(items)} content items]']
        for i, item in enumerate(items, 1):
            fm = item.get('frontmatter', {})
            date = fm.get('pubDate') or fm.get('date') or ''
            draft = ' [DRAFT]' if fm.get('draft') else ''
            featured = ' [FEATURED]' if fm.get('featured') else ''
            lines.append(
                f'{i}. [{item["content_type"]}] "{item["title"]}" '
                f'(slug: {item["slug"]}) — {date}{draft}{featured}'
            )
        injected = '\n'.join(lines)

    Message.objects.create(conversation=conv, role='user', content=injected)

    # Return formatted list directly (no second Claude call)
    if not items:
        type_label = content_type or 'any type'
        return f'No content found of type "{type_label}".'

    display_lines = []
    for i, item in enumerate(items, 1):
        fm = item.get('frontmatter', {})
        date = fm.get('pubDate') or fm.get('date') or ''
        draft = ' (draft)' if fm.get('draft') else ''
        date_suffix = f' — {date}' if date else ''
        display_lines.append(
            f'{i}. **{item["title"]}** (`{item["slug"]}`){date_suffix}{draft}'
        )

    type_label = content_type or 'content'
    header = f'Here are the {type_label} items I found:\n'
    footer = '\nWhich one would you like to view or edit?'

    return header + '\n'.join(display_lines) + footer


def _log_audit(content_type, slug, action, user, sha='', changes_summary=''):
    """Log a content action to the audit trail (if model exists)."""
    if ContentAuditLog is None:
        return
    try:
        ContentAuditLog.objects.create(
            content_type=content_type,
            slug=slug,
            action=action,
            user=user,
            git_commit_sha=sha or '',
            changes_summary=changes_summary,
        )
    except Exception:
        logger.warning('Failed to create audit log entry')


@login_required
@require_POST
def upload_pdf(request, conversation_id):
    """Handle a PDF file upload: extract text/images, inject into conversation, call Claude."""
    conv = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    profile = request.user.profile

    # Rate limiting
    if not _check_rate_limit(request.user):
        return JsonResponse(
            {'error': 'Rate limit exceeded. Please wait before sending more messages.'},
            status=429,
        )

    uploaded = request.FILES.get('pdf')
    if not uploaded:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)

    filename_lower = uploaded.name.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
        return JsonResponse({'error': 'Only PDF and Word (.docx) files are accepted.'}, status=400)

    if uploaded.size > 20 * 1024 * 1024:
        return JsonResponse({'error': 'File exceeds the 20MB size limit.'}, status=400)

    file_bytes = uploaded.read()

    # Save a user message for the upload
    Message.objects.create(
        conversation=conv, role='user',
        content=f'[Uploaded document: {uploaded.name}]',
    )

    # Update conversation title from first message
    if conv.messages.count() <= 1:
        conv.title = f'Document: {uploaded.name[:70]}'
        conv.save(update_fields=['title'])

    # Extract text and images
    is_docx = filename_lower.endswith('.docx')
    doc_label = 'Word document' if is_docx else 'PDF'
    try:
        if is_docx:
            result = extract_docx(file_bytes, uploaded.name)
        else:
            result = extract_pdf(file_bytes, uploaded.name)
        logger.info(
            'Document extracted: %s, type=%s, pages=%s, text_len=%s, images=%s',
            uploaded.name, doc_label, result.get('page_count'), len(result.get('text', '')), len(result.get('images', [])),
        )
    except Exception as exc:
        error_msg = f'Could not process the {doc_label}: {exc}'
        logger.exception('Document extraction failed: %s', uploaded.name)
        Message.objects.create(conversation=conv, role='assistant', content=error_msg)
        return JsonResponse({
            'response': error_msg,
            'conversation_id': str(conv.id),
            'action_taken': None,
        })

    # Save extracted images to temp directory
    saved_images = []
    if result['images']:
        saved_images = save_pdf_images(conv.id, result['images'])

    # Build injected message with extracted content
    text_preview = result['text'][:8000]
    truncated_note = '' if len(result['text']) <= 8000 else '\n\n[Text truncated — full document is longer]'

    image_summary = ''
    if saved_images:
        img_lines = [f'\n\nImages found ({len(saved_images)}):']
        for img in saved_images:
            img_lines.append(f'  - Image {img["index"]}: page {img["page"]}, {img["width"]}x{img["height"]}px ({img["ext"]})')
        image_summary = '\n'.join(img_lines)

    meta = result['metadata']
    meta_lines = ''
    if meta.get('title') or meta.get('author'):
        meta_lines = f'\nDocument Title: {meta["title"]}\nDocument Author: {meta["author"]}\n'

    injected = (
        f'[SYSTEM: {doc_label} "{result["filename"]}" was uploaded and processed — '
        f'{result["page_count"]} page(s)]\n'
        f'{meta_lines}\n'
        f'Extracted text:\n\n{text_preview}{truncated_note}'
        f'{image_summary}'
    )

    Message.objects.create(conversation=conv, role='user', content=injected)

    # Call Claude with the conversation context
    system_prompt = build_system_prompt(profile)
    all_msgs = get_conversation_messages(conv.messages.all())

    try:
        response_text = call_claude(system_prompt, all_msgs)
        action_check = 'CREATE' if '```json' in response_text and '"action": "create"' in response_text else 'questions'
        logger.info('upload_pdf Claude response: conv=%s, action=%s', conv.id, action_check)
    except Exception:
        logger.exception('Claude API call failed after PDF upload')
        error_msg = 'Sorry, I encountered an error processing the PDF. Please try again.'
        Message.objects.create(conversation=conv, role='assistant', content=error_msg)
        return JsonResponse({
            'response': error_msg,
            'conversation_id': str(conv.id),
            'action_taken': None,
        })

    # Check for action blocks in the response (unlikely on first pass, but handle it)
    action_data = extract_action_block(response_text)
    action_result = None

    try:
        if action_data:
            action_type = action_data.get('action')
            if action_type == 'create':
                response_text_extra, action_result = _handle_content_action(
                    action_data, profile, conv, request.user,
                )
                if action_result and action_result.get('type') != 'error':
                    response_text = strip_action_block(response_text) + '\n\n' + response_text_extra
    except Exception:
        logger.exception('Action handling failed after PDF upload: conv=%s', conv.id)
        response_text = 'Sorry, something went wrong while processing the uploaded document. Please try again.'
        action_result = {'type': 'error', 'message': response_text}

    # Build display text: strip action JSON, never leak raw JSON to client
    display_text = strip_action_block(response_text).strip()
    if not display_text:
        if action_result and action_result.get('type') not in (None, 'error'):
            display_text = 'Done! The action has been processed.'
        else:
            display_text = response_text

    # Save to DB exactly what the client will see
    Message.objects.create(conversation=conv, role='assistant', content=display_text)

    return JsonResponse({
        'response': display_text,
        'conversation_id': str(conv.id),
        'action_taken': action_result,
    })


def _save_stripped_message(conv, text):
    """Strip action JSON then save as an assistant message; skip if content is empty."""
    content = strip_action_block(text).strip()
    if content:
        Message.objects.create(conversation=conv, role='assistant', content=content)


_SUBSTACK_URL_RE = re.compile(r'https?://\S*substack\.com\S*')
_GENERAL_URL_RE = re.compile(r'https?://\S+')
_IMAGE_MD_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
_BARE_URL_RE = re.compile(r'^\s*https?://\S+\s*$', re.MULTILINE)

_CONFIRMATIONS = {
    'yes', 'yep', 'yeah', 'yup', 'sure', 'ok', 'okay',
    'create', 'create it', 'go ahead', 'do it', 'add it', 'add',
    'publish', 'confirm', 'proceed', 'please', 'perfect', 'great',
    'yes please', 'yes create it', 'yes add it', 'yes go ahead',
    'sounds good', 'looks good',
}


def _slugify(text):
    """Convert text to a URL-safe slug."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')


def _is_confirmation(message):
    """Return True if message is a simple affirmative confirmation."""
    return message.lower().strip().rstrip(' .,!?') in _CONFIRMATIONS


def _find_scraped_url_data(conv):
    """
    Return (url, scraped_dict) by parsing the [SYSTEM: scraped] message already in
    the conversation DB, or (None, None) if none found or article already created.
    """
    # Don't double-create if already done in this conversation
    if conv.messages.filter(role='assistant', content__icontains='successfully created').exists():
        return None, None

    msg = conv.messages.filter(
        role='user',
        content__startswith='[SYSTEM: The URL ',
    ).order_by('created_at').first()
    if not msg:
        return None, None

    header_match = re.match(r'\[SYSTEM: The URL (.+?) was scraped\.', msg.content)
    if not header_match:
        return None, None
    url = header_match.group(1)

    data = {'source_url': url, 'title': '', 'author': '', 'date': '',
            'publication': '', 'image_url': '', 'body_markdown': ''}

    for line in msg.content.splitlines():
        if line.startswith('Title: '):
            data['title'] = line[7:].strip()
        elif line.startswith('Author: '):
            data['author'] = line[8:].strip()
        elif line.startswith('Date: '):
            data['date'] = line[6:].strip()
        elif line.startswith('Publication: '):
            data['publication'] = line[13:].strip()
        elif line.startswith('Image URL: '):
            data['image_url'] = line[11:].strip()

    body_marker = '\nArticle body (markdown):\n\n'
    idx = msg.content.find(body_marker)
    if idx != -1:
        data['body_markdown'] = msg.content[idx + len(body_marker):]

    return url, data


def _direct_briefing_from_scraped(url, scraped, profile, conv, user):
    """
    Create a briefing directly from scraped URL data — no Claude call.
    Constructs action_data and delegates to _handle_content_action.
    Returns (response_text, action_result).
    """
    from datetime import date as _date

    title = scraped.get('title') or 'Untitled'
    slug = _slugify(title) or 'briefing'
    source_author = scraped.get('author') or ''
    raw_date = scraped.get('date') or _date.today().isoformat()
    pub_date = f'{raw_date}T00:00:00.000Z'
    image_url = scraped.get('image_url') or ''
    publication = scraped.get('publication') or ''
    body = scraped.get('body_markdown') or ''

    frontmatter = {
        'title': title,
        'slug': slug,
        'author': source_author or 'MMTUK',
        'pubDate': pub_date,
        'readTime': 5,
        'sourceUrl': url,
        'sourceTitle': title,
        'sourceDate': raw_date,
    }
    if source_author:
        frontmatter['sourceAuthor'] = source_author
    if publication:
        frontmatter['sourcePublication'] = publication
    if image_url:
        frontmatter['thumbnail'] = f'/media/images/briefings/{slug}-thumbnail.webp'

    action_data = {
        'action': 'create',
        'content_type': 'briefing',
        'frontmatter': frontmatter,
        'body': body,
    }
    if image_url:
        action_data['images'] = [{'url': image_url}]

    logger.info('direct_briefing: creating "%s" (slug=%s) from %s', title, slug, url)
    return _handle_content_action(action_data, profile, conv, user)


def _pre_scrape_url(user_message, conv):
    """
    If the user message contains a URL that hasn't been scraped yet in
    this conversation, scrape it and inject the content as a system message.
    Returns the scraped data dict on success, or None if not applicable/failed.
    The caller can use the returned data to skip the Claude API call entirely.
    """
    match = _GENERAL_URL_RE.search(user_message)
    if not match:
        return None

    url = match.group(0).rstrip('.,;!?)')

    # Skip if this URL was already scraped in this conversation
    if conv.messages.filter(
        role='user',
        content__startswith=f'[SYSTEM: The URL {url} was scraped',
    ).exists():
        return None

    try:
        import concurrent.futures
        t = time.monotonic()
        logger.info('pre_scrape: start url=%s', url)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scrape_url, url)
            try:
                scraped = future.result(timeout=60)
            except concurrent.futures.TimeoutError:
                logger.warning('pre_scrape: timed out after 60s for %s', url)
                return None
        logger.info('pre_scrape timing: %.1fs for %s', time.monotonic() - t, url)

        scraped_summary = (
            f'[SYSTEM: The URL {url} was scraped. Here is the extracted data]\n\n'
            f'Title: {scraped.get("title", "")}\n'
            f'Author: {scraped.get("author", "")}\n'
            f'Date: {scraped.get("date", "")}\n'
            f'Publication: {scraped.get("publication", "")}\n'
            f'Image URL: {scraped.get("image_url", "")}\n\n'
            f'Article body (markdown):\n\n{scraped.get("body_markdown", "")}'
        )
        Message.objects.create(conversation=conv, role='user', content=scraped_summary)
        return scraped  # Return data so caller can skip Claude for this message
    except Exception:
        logger.warning('Pre-scrape failed for %s', url, exc_info=True)
        return None


def _format_scrape_preview(scraped):
    """Format a scraped article as a chat preview without calling Claude."""
    title = scraped.get('title') or 'Unknown title'
    author = scraped.get('author') or ''
    date = scraped.get('date', '')
    publication = scraped.get('publication', '')
    body_text = scraped.get('body_markdown') or ''

    # Strip image markdown and bare URLs before taking the preview slice
    clean_body = _IMAGE_MD_RE.sub('', body_text)
    clean_body = _BARE_URL_RE.sub('', clean_body)
    clean_body = clean_body.strip()
    body_preview = clean_body[:300].strip()

    lines = [f'**{title}**']
    if author:
        lines.append(f'By {author}')
    if date:
        lines.append(f'Published: {date}')
    if publication:
        lines.append(f'Publication: {publication}')
    if body_preview:
        lines.append('')
        lines.append(body_preview + ('...' if len(clean_body) > 300 else ''))
    lines.append('')
    lines.append("I've scraped the content above. What would you like me to do with it? For example: create a briefing, add as an article, create a local event, or something else?")
    return '\n'.join(lines)


@login_required
@require_POST
def send_message(request, conversation_id):
    """Handle a chat message from the user."""
    logger.info('send_message: arrived conv=%s user=%s', conversation_id, request.user.username)
    conv = get_object_or_404(Conversation, id=conversation_id, user=request.user)
    profile = request.user.profile

    # Rate limiting
    if not _check_rate_limit(request.user):
        return JsonResponse(
            {'error': 'Rate limit exceeded. Please wait before sending more messages.'},
            status=429,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'error': 'Empty message'}, status=400)

    # Save user message
    Message.objects.create(conversation=conv, role='user', content=user_message)

    # Update conversation title from first message
    if conv.messages.count() <= 1:
        conv.title = user_message[:80]
        conv.save(update_fields=['title'])

    # STEP 2: URL detected → scrape and inject data into conversation history.
    # Then fall through to Claude so it can respond in context (using what it already
    # knows from earlier in the conversation — e.g. "this is a local event for London").
    url_match = _GENERAL_URL_RE.search(user_message)
    if url_match:
        _pre_scrape_url(user_message, conv)
        # Fall through to Claude regardless of scrape success/failure

    # STEP 3: Call Claude with full conversation history (including any scraped data).
    # Build messages and call Claude
    try:
        t_prompt = time.monotonic()
        system_prompt = build_system_prompt(profile)
        logger.info('send_message timing: build_prompt=%.1fs', time.monotonic() - t_prompt)
        all_msgs = get_conversation_messages(conv.messages.all())
        logger.info('send_message: conv=%s, history_len=%s, msg_preview=%.80r', conv.id, len(all_msgs), user_message)
        t_claude = time.monotonic()
        response_text = call_claude(system_prompt, all_msgs)
        logger.info('send_message timing: claude_api=%.1fs', time.monotonic() - t_claude)
    except Exception:
        logger.exception('Claude API call failed')
        error_msg = 'Sorry, I encountered an error. Please try again.'
        Message.objects.create(conversation=conv, role='assistant', content=error_msg)
        return JsonResponse({
            'response': error_msg,
            'conversation_id': str(conv.id),
            'action_taken': None,
        })

    # Check for action blocks
    action_data = extract_action_block(response_text)
    action_result = None

    try:
        if action_data:
            action_type = action_data.get('action')

            if action_type == 'scrape':
                # Save Claude's initial response (skip if empty after stripping)
                _save_stripped_message(conv, response_text)

                # Handle scraping — returns formatted preview (no second Claude call)
                response_text = _handle_scrape_action(action_data, profile, conv)

            elif action_type == 'create':
                response_text_extra, action_result = _handle_content_action(
                    action_data, profile, conv, request.user,
                )
                preamble = strip_action_block(response_text).strip()
                response_text = f'{preamble}\n\n{response_text_extra}' if preamble else response_text_extra

            elif action_type == 'read':
                # Save Claude's initial response (skip if empty after stripping)
                _save_stripped_message(conv, response_text)

                # Handle read — returns formatted summary (no second Claude call)
                response_text = _handle_read_action(action_data, profile, conv)

            elif action_type == 'edit':
                response_text_extra, action_result = _handle_edit_action(
                    action_data, profile, conv, request.user,
                )
                preamble = strip_action_block(response_text).strip()
                response_text = f'{preamble}\n\n{response_text_extra}' if preamble else response_text_extra

            elif action_type == 'delete':
                response_text_extra, action_result = _handle_delete_action(
                    action_data, profile, conv, request.user,
                )
                preamble = strip_action_block(response_text).strip()
                response_text = f'{preamble}\n\n{response_text_extra}' if preamble else response_text_extra

            elif action_type == 'list':
                # Save Claude's initial response (skip if empty after stripping)
                _save_stripped_message(conv, response_text)

                # Handle list — returns formatted list (no second Claude call)
                response_text = _handle_list_action(action_data, profile, conv)

    except Exception:
        logger.exception('Action handling failed: conv=%s', conv.id)
        response_text = 'Sorry, something went wrong while processing that action. Please try again.'
        action_result = {'type': 'error', 'message': response_text}

    # Build display text: strip action JSON, never leak raw JSON to client
    display_text = strip_action_block(response_text).strip()
    if not display_text:
        if action_result and action_result.get('type') not in (None, 'error'):
            display_text = 'Done! The action has been processed.'
        else:
            display_text = response_text

    # Save to DB exactly what the client will see (so page reloads are consistent)
    Message.objects.create(conversation=conv, role='assistant', content=display_text)

    logger.info(
        'send_message complete: conv=%s, action=%s, response_len=%d',
        conv.id,
        action_result.get('type') if action_result else None,
        len(display_text),
    )
    return JsonResponse({
        'response': display_text,
        'conversation_id': str(conv.id),
        'action_taken': action_result,
    })


# --- Pending approvals views ---

@login_required
def pending_list(request):
    """List pending content drafts for review."""
    profile = request.user.profile
    if not profile.can_approve():
        return HttpResponseForbidden('You do not have permission to view pending drafts.')

    drafts = ContentDraft.objects.filter(status='pending')

    # Group leads only see their own group's content
    if profile.role == 'group_lead':
        drafts = drafts.filter(
            content_type__in=['local_event', 'local_news'],
            frontmatter_json__localGroup=profile.local_group,
        )

    return render(request, 'chat/pending.html', {
        'drafts': drafts,
        'profile': profile,
    })


@login_required
def pending_detail(request, draft_id):
    """View a single pending draft."""
    profile = request.user.profile
    if not profile.can_approve():
        return HttpResponseForbidden('You do not have permission to view pending drafts.')

    draft = get_object_or_404(ContentDraft, id=draft_id, status='pending')

    # Build a preview from the draft's frontmatter and body
    fm_lines = '\n'.join(f'{k}: {v}' for k, v in draft.frontmatter_json.items())
    markdown_preview = f'---\n{fm_lines}\n---\n\n{draft.body_markdown or ""}'

    return render(request, 'chat/pending_detail.html', {
        'draft': draft,
        'markdown_preview': markdown_preview,
        'profile': profile,
    })


@login_required
@require_POST
def approve_draft(request, draft_id):
    """Approve and publish a pending draft."""
    profile = request.user.profile
    draft = get_object_or_404(ContentDraft, id=draft_id, status='pending')

    local_group = draft.frontmatter_json.get('localGroup', '')
    if not profile.can_approve(draft.content_type, local_group):
        return HttpResponseForbidden('You do not have permission to approve this content.')

    try:
        # Check if this is an edit (slug already exists) or a new creation
        if check_slug_exists(draft.content_type, draft.slug):
            instance, errors = update_content(
                draft.content_type, draft.slug,
                draft.frontmatter_json, draft.body_markdown,
            )
        else:
            instance, errors = create_content(
                draft.content_type, draft.frontmatter_json,
                draft.body_markdown, status='published',
            )

        if errors:
            return JsonResponse({'error': 'Validation errors: ' + '; '.join(errors)}, status=400)

        # Write image if present
        if draft.image_data and draft.image_path:
            image_save_path, image_web_path = get_image_save_path(
                draft.content_type, draft.slug,
            )
            image_save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(image_save_path, 'wb') as f:
                f.write(bytes(draft.image_data))
            if image_web_path and instance:
                _update_image_field(instance, draft.content_type, image_web_path)

        draft.status = 'approved'
        draft.reviewer = request.user
        draft.reviewed_at = timezone.now()
        draft.git_commit_sha = ''
        draft.save()

        _log_audit(draft.content_type, draft.slug, 'approve', request.user, '')

        return redirect('pending_list')

    except Exception:
        logger.exception('Failed to publish approved draft')
        return JsonResponse({'error': 'Failed to publish. Please try again.'}, status=500)


@login_required
@require_POST
def reject_draft(request, draft_id):
    """Reject a pending draft with optional feedback."""
    profile = request.user.profile
    draft = get_object_or_404(ContentDraft, id=draft_id, status='pending')

    local_group = draft.frontmatter_json.get('localGroup', '')
    if not profile.can_approve(draft.content_type, local_group):
        return HttpResponseForbidden('You do not have permission to reject this content.')

    feedback = request.POST.get('feedback', '')

    draft.status = 'rejected'
    draft.reviewer = request.user
    draft.reviewed_at = timezone.now()
    draft.review_feedback = feedback
    draft.save()

    return redirect('pending_list')


# --- Content Browser views ---

@login_required
def content_browser(request):
    """Main content browser view showing all content in a card grid."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]
    content_type_filter = request.GET.get('type', '')
    sort_by = request.GET.get('sort', 'date_desc')
    query = request.GET.get('q', '')
    view_mode = request.GET.get('view', 'list')

    if query:
        items = search_content(query, content_type_filter or None)
    else:
        items = list_content(content_type_filter or None)

    # Sort items
    if sort_by == 'date_asc':
        items = sorted(items, key=lambda x: _sort_date(x))
    elif sort_by == 'title_asc':
        items = sorted(items, key=lambda x: x.get('title', '').lower())
    elif sort_by == 'title_desc':
        items = sorted(items, key=lambda x: x.get('title', '').lower(), reverse=True)
    else:  # date_desc (default)
        items = sorted(items, key=lambda x: _sort_date(x), reverse=True)

    # Enrich items with computed fields for safe template access
    for item in items:
        fm = item.get('frontmatter', {})
        item['summary'] = fm.get('summary') or fm.get('description') or fm.get('text') or ''
        item['author'] = fm.get('author') or fm.get('sourceAuthor') or fm.get('name') or ''
        item['date'] = fm.get('pubDate') or fm.get('date') or item.get('created_at') or ''
        # Normalise: if YAML left an ISO datetime string unparsed, convert it now
        if isinstance(item['date'], str) and item['date']:
            try:
                from datetime import datetime as _dt
                item['date'] = _dt.fromisoformat(item['date'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        item['is_draft'] = fm.get('draft', False)
        item['is_featured'] = fm.get('featured', False)
        item['thumbnail'] = fm.get('thumbnail') or fm.get('image') or ''

    stats = get_content_stats()

    from .services.content_reader_service import CONTENT_TYPE_NAMES
    type_choices = [(k, CONTENT_TYPE_NAMES.get(k, k)) for k in MODEL_MAP.keys()]

    return render(request, 'chat/content_browser.html', {
        'conversations': conversations,
        'items': items,
        'stats': stats,
        'content_type_filter': content_type_filter,
        'sort_by': sort_by,
        'query': query,
        'type_choices': type_choices,
        'view_mode': view_mode,
        'profile': profile,
        'active_tab': 'content',
    })


def _sort_date(item):
    """Extract a sortable date string from a content item."""
    fm = item.get('frontmatter', {})
    d = fm.get('pubDate') or fm.get('date') or ''
    if not d:
        # Fall back to created_at for content types without a publication date
        d = item.get('created_at', '')
    if isinstance(d, datetime):
        return d.isoformat()
    return str(d) if d else '0000'


@login_required
@permission_required('accounts.can_view_content', raise_exception=True)
def event_archive(request):
    """View archived events (ended more than 7 days ago)."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]
    sort_by = request.GET.get('sort', 'date_desc')
    query = request.GET.get('q', '')

    # Get all local events
    if query:
        items = search_content(query, 'local_event')
    else:
        items = list_content('local_event')

    # Filter for archived events only
    archived_items = [item for item in items if item.get('frontmatter', {}).get('archived', False)]

    # Sort items
    if sort_by == 'date_asc':
        archived_items = sorted(archived_items, key=lambda x: _sort_date(x))
    elif sort_by == 'title_asc':
        archived_items = sorted(archived_items, key=lambda x: x.get('title', '').lower())
    elif sort_by == 'title_desc':
        archived_items = sorted(archived_items, key=lambda x: x.get('title', '').lower(), reverse=True)
    else:  # date_desc (default)
        archived_items = sorted(archived_items, key=lambda x: _sort_date(x), reverse=True)

    # Enrich items with computed fields
    for item in archived_items:
        fm = item.get('frontmatter', {})
        item['summary'] = fm.get('description') or ''
        item['date'] = fm.get('date') or ''
        item['end_date'] = fm.get('endDate') or fm.get('date') or ''
        item['local_group'] = fm.get('localGroup') or ''
        item['location'] = fm.get('location') or ''
        item['tag'] = fm.get('tag') or ''

    return render(request, 'chat/event_archive.html', {
        'conversations': conversations,
        'archived_events': archived_items,
        'sort_by': sort_by,
        'query': query,
        'profile': profile,
        'active_tab': 'content',
    })


@login_required
@permission_required('accounts.can_approve_content', raise_exception=True)
@require_http_methods(["POST"])
def unarchive_event(request, content_type, slug):
    """Unarchive an event (admin/editor only)."""
    from django.contrib import messages
    from django.shortcuts import redirect

    # Only allow for local_event content type
    if content_type != 'local_event':
        messages.error(request, 'Only events can be unarchived.')
        return redirect('content_detail', content_type=content_type, slug=slug)

    # Read the event
    item = read_content(content_type, slug)
    if not item:
        messages.error(request, 'Event not found.')
        return redirect('event_archive')

    # Check if already unarchived
    if not item.get('frontmatter', {}).get('archived', False):
        messages.info(request, 'Event is already active (not archived).')
        return redirect('content_detail', content_type=content_type, slug=slug)

    # Update via ORM
    try:
        instance, errors = update_content(content_type, slug, {'archived': False})
        if errors:
            messages.error(request, f'Failed to unarchive: {"; ".join(errors)}')
            return redirect('content_detail', content_type=content_type, slug=slug)
    except Exception:
        logger.exception('Failed to unarchive event %s', slug)
        messages.error(request, 'Failed to unarchive event.')
        return redirect('content_detail', content_type=content_type, slug=slug)

    title = item.get('frontmatter', {}).get('title', slug)

    # Log audit
    _log_audit(content_type, slug, 'unarchive', request.user, '')

    messages.success(request, f'Event unarchived: {title}')
    return redirect('content_detail', content_type=content_type, slug=slug)


@login_required
def content_detail(request, content_type, slug):
    """View a single content item with full details."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]

    item = read_content(content_type, slug)
    if not item:
        from django.http import Http404
        raise Http404(f'Content not found: {content_type}/{slug}')

    # Build route info for site URL
    _CONTENT_ROUTES = {
        'article': '/articles/{slug}',
        'briefing': '/research/briefings/{slug}',
        'news': '/news/{slug}',
        'ecosystem': '/ecosystem/{slug}',
        'local_group': '/local-group/{slug}',
        'local_event': '/local-group/{localGroup}/{slug}',
    }

    title = (
        item['frontmatter'].get('title')
        or item['frontmatter'].get('heading')
        or item['frontmatter'].get('name')
        or 'Untitled'
    )

    # Build site URL
    route = _CONTENT_ROUTES.get(content_type, '')
    site_url = ''
    if route and '{slug}' in route:
        try:
            site_url = 'https://mmtuk.org' + route.format(
                slug=slug,
                localGroup=item['frontmatter'].get('localGroup', ''),
            )
        except (KeyError, AttributeError):
            site_url = ''

    # Get audit log entries for this item (if model exists)
    audit_entries = []
    if ContentAuditLog is not None:
        try:
            audit_entries = list(ContentAuditLog.objects.filter(
                content_type=content_type, slug=slug,
            ).order_by('-created_at')[:20])
        except Exception:
            pass

    # Determine if content has been published (pushed to remote)
    is_published = True  # assume published for pre-CMS content
    if site_url and audit_entries:
        latest_action = audit_entries[0]
        if latest_action.git_commit_sha:
            is_published = ContentAuditLog.objects.filter(
                content_type='site', action='publish',
                created_at__gte=latest_action.created_at,
            ).exists()

    return render(request, 'chat/content_detail.html', {
        'conversations': conversations,
        'item': item,
        'content_type': content_type,
        'slug': slug,
        'title': title,
        'site_url': site_url,
        'is_published': is_published,
        'profile': profile,
        'audit_entries': audit_entries,
        'active_tab': 'content',
    })


@login_required
def content_api(request):
    """JSON API for dynamic content filtering (used by browser JS)."""
    content_type_filter = request.GET.get('type', '')
    sort_by = request.GET.get('sort', 'date_desc')
    query = request.GET.get('q', '')

    if query:
        items = search_content(query, content_type_filter or None)
    else:
        items = list_content(content_type_filter or None)

    # Sort
    if sort_by == 'date_asc':
        items = sorted(items, key=lambda x: _sort_date(x))
    elif sort_by == 'title_asc':
        items = sorted(items, key=lambda x: x.get('title', '').lower())
    elif sort_by == 'title_desc':
        items = sorted(items, key=lambda x: x.get('title', '').lower(), reverse=True)
    else:
        items = sorted(items, key=lambda x: _sort_date(x), reverse=True)

    # Serialize for JSON
    result = []
    for item in items:
        fm = item.get('frontmatter', {})
        result.append({
            'content_type': item['content_type'],
            'slug': item['slug'],
            'title': item['title'],
            'date': _sort_date(item),
            'author': fm.get('author', fm.get('sourceAuthor', '')),
            'category': fm.get('category', ''),
            'thumbnail': fm.get('thumbnail', fm.get('image', '')),
            'draft': fm.get('draft', False),
            'featured': fm.get('featured', False),
        })

    return JsonResponse({'items': result})


@login_required
def edit_in_chat(request, content_type, slug):
    """Create a new conversation pre-loaded with edit context for a content item."""
    item = read_content(content_type, slug)
    if not item:
        from django.http import Http404
        raise Http404(f'Content not found: {content_type}/{slug}')

    title = (
        item['frontmatter'].get('title')
        or item['frontmatter'].get('heading')
        or item['frontmatter'].get('name')
        or 'Untitled'
    )

    # Create a conversation with a pre-loaded message
    conv = Conversation.objects.create(
        user=request.user,
        title=f'Edit: {title[:70]}',
    )

    # Save a system-injected user message with the content context
    context_msg = (
        f'I want to edit the existing {content_type} "{title}" (slug: {slug}).\n\n'
        f'Please load the current content so we can discuss changes.'
    )
    Message.objects.create(conversation=conv, role='user', content=context_msg)

    return redirect('conversation', conversation_id=conv.id)


@login_required
@require_POST
def quick_edit(request, content_type, slug):
    """Handle quick-edit form submission from content detail page."""
    profile = request.user.profile

    if not profile.can_edit(content_type):
        return HttpResponseForbidden('You do not have permission to edit content.')

    # Read existing content
    existing = read_content(content_type, slug)
    if not existing:
        from django.http import Http404
        raise Http404(f'Content not found: {content_type}/{slug}')

    # Collect frontmatter updates from form fields (prefixed with fm_)
    updated_fm = {}
    for key in list(existing['frontmatter'].keys()):
        form_key = f'fm_{key}'
        if form_key in request.POST:
            value = request.POST[form_key]
            if value == '':
                value = None
            else:
                # Coerce boolean and number types
                if isinstance(value, str) and value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif isinstance(value, str):
                    try:
                        value = int(value) if '.' not in value else float(value)
                    except (ValueError, TypeError):
                        pass  # leave as string
            if value is not None:
                updated_fm[key] = value

    # Get body
    new_body = request.POST.get('body', None)

    try:
        instance, errors = update_content(content_type, slug, updated_fm, new_body)
        if errors:
            from django.contrib import messages
            messages.error(request, f'Validation errors: {"; ".join(errors)}')
            return redirect('content_detail', content_type=content_type, slug=slug)

        _log_audit(content_type, slug, 'edit', request.user, '')

        # For local events: if image is set but file missing (and link is available), fetch it
        if content_type == 'local_event' and instance:
            _ensure_event_image(instance)

    except Exception:
        logger.exception('Quick edit failed')

    return redirect('content_detail', content_type=content_type, slug=slug)


@login_required
@require_POST
def delete_content_view(request, content_type, slug):
    """Delete content from the content browser with redirect tracking."""
    profile = request.user.profile

    if not profile.can_delete(content_type):
        return HttpResponseForbidden('You do not have permission to delete content.')

    existing = read_content(content_type, slug)
    if not existing:
        from django.http import Http404
        raise Http404(f'Content not found: {content_type}/{slug}')

    title = (
        existing['frontmatter'].get('title')
        or existing['frontmatter'].get('heading')
        or existing['frontmatter'].get('name')
        or 'Untitled'
    )

    # Get redirect target from form (empty string means intentional 404)
    redirect_target = request.POST.get('redirect_target', '').strip()

    try:
        success, error = delete_content_orm(content_type, slug)
        if not success:
            from django.contrib import messages
            messages.error(request, f'Failed to delete: {error}')
            return redirect('content_browser')

        # Log deletion with redirect tracking
        ContentAuditLog.objects.create(
            content_type=content_type,
            slug=slug,
            action='delete',
            user=request.user,
            git_commit_sha='',
            changes_summary=f'Deleted: {title}',
            deleted_at=timezone.now(),
            redirect_target=redirect_target,
        )

        # Show success message with redirect info
        from django.contrib import messages
        if redirect_target:
            messages.success(
                request,
                f'Content deleted. Visitors will be redirected to: {redirect_target}'
            )
        else:
            messages.success(
                request,
                f'Content deleted. Old URL will return 404 (no redirect).'
            )

    except Exception:
        logger.exception('Delete content failed')

    return redirect('content_browser')


# --- Media Library views ---

@login_required
def media_library(request):
    """Media library showing all images with upload capability."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]
    subdirectory = request.GET.get('dir', '')
    view_mode = request.GET.get('view', 'sections')

    images = list_images(subdirectory or None)
    grouped = _group_responsive_variants(images)

    # Can upload: admin, editor, group_lead
    can_upload = profile.role in ('admin', 'editor', 'group_lead')

    # Build hierarchical section data (unless flat view requested)
    sections = []
    if view_mode != 'flat':
        sections = categorise_images(images)

    return render(request, 'chat/media_library.html', {
        'conversations': conversations,
        'images': grouped,
        'sections': sections,
        'profile': profile,
        'can_upload': can_upload,
        'current_dir': subdirectory,
        'view_mode': view_mode,
        'active_tab': 'content',
    })


@login_required
@require_POST
def upload_image(request):
    """Handle image upload to the repo's public/images/ directory."""
    profile = request.user.profile

    if profile.role not in ('admin', 'editor', 'group_lead'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    uploaded = request.FILES.get('image')
    if not uploaded:
        return JsonResponse({'error': 'No image file uploaded.'}, status=400)

    # Validate file type
    allowed_types = {'image/png', 'image/jpeg', 'image/webp', 'image/avif', 'image/gif', 'image/svg+xml'}
    if uploaded.content_type not in allowed_types:
        return JsonResponse({'error': f'Unsupported image type: {uploaded.content_type}'}, status=400)

    if uploaded.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Image exceeds the 10MB size limit.'}, status=400)

    # Determine save path
    save_dir = request.POST.get('directory', 'images')
    filename = request.POST.get('filename', uploaded.name)
    # Sanitise filename
    filename = filename.replace('\\', '/').split('/')[-1]
    filename = ''.join(c for c in filename if c.isalnum() or c in '.-_').strip()
    if not filename:
        filename = 'upload.webp'

    image_bytes = uploaded.read()

    # Optimize to WebP (skip SVG)
    if uploaded.content_type != 'image/svg+xml':
        from .services.image_service import optimize_image
        try:
            image_bytes = optimize_image(image_bytes, max_width=1200)
            filename = filename.rsplit('.', 1)[0] + '.webp'
        except Exception:
            pass  # Keep original format

    # Save to MEDIA_ROOT/images/ — block directory traversal
    from pathlib import Path
    media_root = Path(settings.MEDIA_ROOT).resolve()
    save_path = (media_root / save_dir.strip('/') / filename).resolve()
    if not str(save_path).startswith(str(media_root)):
        return JsonResponse({'error': 'Invalid directory.'}, status=400)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(save_path, 'wb') as f:
            f.write(image_bytes)

        # Web path for use in frontmatter
        web_path = '/' + save_dir.strip('/') + '/' + filename

        return JsonResponse({
            'success': True,
            'path': str(save_path),
            'web_path': web_path,
            'filename': filename,
        })

    except Exception:
        logger.exception('Image upload failed')
        return JsonResponse({'error': 'Failed to upload image.'}, status=500)


def _find_image_references(web_path):
    """Return list of {content_type, slug, title} for items whose frontmatter references web_path."""
    refs = []
    for item in list_content():
        fm = item.get('frontmatter', {})
        for field in ('thumbnail', 'image', 'photo', 'heroImage'):
            if fm.get(field) == web_path:
                refs.append({
                    'content_type': item['content_type'],
                    'slug': item['slug'],
                    'title': item['title'],
                })
                break
    return refs


@login_required
@require_POST
def delete_image(request):
    """Delete an image from the repo's public/images/ directory."""
    profile = request.user.profile

    if profile.role not in ('admin', 'editor', 'group_lead'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    web_path = request.POST.get('web_path', '').strip()
    if not web_path.startswith('/images/') or '..' in web_path:
        return JsonResponse({'error': 'Invalid path'}, status=400)

    # Reference check — warn before deleting images used by content items
    force = request.POST.get('force') == '1'
    if not force:
        refs = _find_image_references(web_path)
        if refs:
            return JsonResponse({'warning': True, 'references': refs})

    filename = web_path.rsplit('/', 1)[-1]

    try:
        from pathlib import Path

        # Try MEDIA_ROOT first, then static images dir
        media_path = Path(settings.MEDIA_ROOT) / web_path.lstrip('/')
        static_path = Path(settings.BASE_DIR) / 'content' / 'static' / 'content' / web_path.lstrip('/')

        deleted = False
        for full_path in (media_path, static_path):
            if full_path.exists():
                full_path.unlink()
                deleted = True
                break

        if not deleted:
            return JsonResponse({'error': 'Image not found'}, status=404)

        return JsonResponse({'success': True})

    except Exception:
        logger.exception('Image delete failed for %s', web_path)
        return JsonResponse({'error': 'Failed to delete image.'}, status=500)


@login_required
def images_api(request):
    """Return deduplicated image list, collapsing responsive variants."""
    directory = request.GET.get('directory', '')
    images = list_images(directory=directory or None)
    grouped = _group_responsive_variants(images)
    return JsonResponse({'images': [
        {'web_path': g['primary']['web_path'], 'filename': g['base_filename']}
        for g in grouped if g['primary']
    ]})


# --- Repo image serving ---

@login_required
def repo_image(request, image_path):
    """Serve an image from MEDIA_ROOT or static content images."""
    import mimetypes
    from pathlib import Path

    # Prevent path traversal
    clean = Path(image_path).as_posix()
    if '..' in clean:
        raise Http404

    # Try MEDIA_ROOT first
    full_path = Path(settings.MEDIA_ROOT) / clean

    if not full_path.exists() or not full_path.is_file():
        # Fallback to static content images
        full_path = Path(settings.BASE_DIR) / 'content' / 'static' / 'content' / clean
        if not full_path.exists() or not full_path.is_file():
            logger.warning('repo_image: 404 path=%s', image_path)
            raise Http404

    # Fallback MIME types for formats Python's mimetypes may not know
    _EXTRA_MIME = {'.avif': 'image/avif', '.webp': 'image/webp', '.heic': 'image/heic'}
    content_type, _ = mimetypes.guess_type(str(full_path))
    if not content_type:
        content_type = _EXTRA_MIME.get(full_path.suffix.lower(), 'application/octet-stream')
    return FileResponse(open(full_path, 'rb'), content_type=content_type)


# --- Featured toggle API ---

@login_required
@require_POST
def toggle_featured(request, content_type, slug):
    """Toggle the 'featured' field on a content item."""
    profile = request.user.profile
    if not profile.can_edit(content_type):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        Model = get_model_class(content_type)
        instance = Model.objects.get(slug=slug)
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({'error': 'Content not found'}, status=404)

    if not hasattr(instance, 'featured'):
        return JsonResponse({'error': 'This content type does not support featured.'}, status=400)

    instance.featured = not instance.featured
    instance.save(update_fields=['featured'])

    _log_audit(content_type, slug, 'edit', request.user, '', f'featured={instance.featured}')

    return JsonResponse({'success': True, 'featured': instance.featured})


# --- Content Health Check ---

@login_required
def content_health(request):
    """Content health check dashboard."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]

    if profile.role not in ('admin', 'editor'):
        return HttpResponseForbidden('You do not have permission to view health checks.')

    all_content = list_content()
    all_images = list_images()
    image_paths = {img['web_path'] for img in all_images}

    issues = {
        'missing_thumbnails': [],
        'placeholder_images': [],
        'stale_drafts': [],
        'missing_fields': [],
    }

    for item in all_content:
        fm = item.get('frontmatter', {})
        ct = item['content_type']
        title = item['title']

        # Check for missing thumbnails
        thumb = fm.get('thumbnail') or fm.get('image') or fm.get('photo', '')
        if thumb and thumb not in image_paths and not thumb.startswith('http'):
            issues['missing_thumbnails'].append({
                'title': title,
                'content_type': ct,
                'slug': item['slug'],
                'path': thumb,
            })

        # Check for placeholder images
        if thumb and 'placeholder' in thumb.lower():
            issues['placeholder_images'].append({
                'title': title,
                'content_type': ct,
                'slug': item['slug'],
                'path': thumb,
            })

        # Check for stale drafts
        if fm.get('draft') is True:
            issues['stale_drafts'].append({
                'title': title,
                'content_type': ct,
                'slug': item['slug'],
            })

    return render(request, 'chat/content_health.html', {
        'conversations': conversations,
        'issues': issues,
        'total_content': len(all_content),
        'total_images': len(all_images),
        'profile': profile,
        'active_tab': 'content',
    })


# --- Bulk Operations ---

@login_required
@require_POST
def bulk_action(request):
    """Handle bulk operations on selected content items."""
    profile = request.user.profile
    if profile.role not in ('admin', 'editor'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    action = data.get('action', '')
    items = data.get('items', [])

    if not items:
        return JsonResponse({'error': 'No items selected'}, status=400)

    results = {'success': 0, 'errors': 0}

    for item_ref in items:
        ct = item_ref.get('content_type', '')
        slug = item_ref.get('slug', '')
        if not ct or not slug:
            results['errors'] += 1
            continue

        if action == 'delete':
            try:
                success, error = delete_content_orm(ct, slug)
                if success:
                    _log_audit(ct, slug, 'delete', request.user)
                    results['success'] += 1
                else:
                    results['errors'] += 1
            except Exception:
                logger.exception('Bulk delete failed for %s/%s', ct, slug)
                results['errors'] += 1

        elif action == 'set_draft':
            try:
                Model = get_model_class(ct)
                instance = Model.objects.get(slug=slug)
                if hasattr(instance, 'draft'):
                    instance.draft = True
                    instance.save(update_fields=['draft'])
                elif hasattr(instance, 'status'):
                    instance.status = 'draft'
                    instance.save(update_fields=['status'])
                results['success'] += 1
            except Exception:
                results['errors'] += 1

        elif action == 'unset_draft':
            try:
                Model = get_model_class(ct)
                instance = Model.objects.get(slug=slug)
                if hasattr(instance, 'draft'):
                    instance.draft = False
                    instance.save(update_fields=['draft'])
                elif hasattr(instance, 'status'):
                    instance.status = 'published'
                    instance.save(update_fields=['status'])
                results['success'] += 1
            except Exception:
                results['errors'] += 1

    return JsonResponse(results)


# --- Activity Log ---

@login_required
def review_changes(request):
    """Review pending drafts and recent audit activity."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]

    pending_drafts = ContentDraft.objects.filter(status='pending')

    # Scope for group leads
    if profile.role == 'group_lead' and profile.local_group:
        pending_drafts = pending_drafts.filter(
            frontmatter_json__localGroup=profile.local_group
        )

    recent_audit = ContentAuditLog.objects.select_related('user')[:20]

    return render(request, 'chat/review_changes.html', {
        'pending_drafts': pending_drafts,
        'pending_count': pending_drafts.count(),
        'recent_audit': recent_audit,
        'conversations': conversations,
        'profile': profile,
    })


# --- Discard conversation ---

@login_required
@require_POST
def discard_conversation(request, conversation_id):
    """
    Discard an in-progress conversation and clean up unpublished work.

    This view:
    1. Deletes all pending ContentDraft records linked to the conversation
    2. Resets unpushed commits associated with those drafts (using git reset --soft)
    3. Marks the conversation as discarded
    4. Redirects to content browser with a success message

    Edge cases handled:
    - Only allows discarding if user owns the conversation or is admin
    - Prevents discarding if commits are already pushed
    - Preserves file changes when resetting commits (soft reset)
    """
    from django.contrib import messages

    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Permission check: user must own conversation or be admin
    if conversation.user != request.user and request.user.profile.role != 'admin':
        return HttpResponseForbidden('You do not have permission to discard this conversation.')

    # Check if conversation is already discarded
    if conversation.discarded_at:
        messages.warning(request, 'This conversation was already discarded.')
        return redirect('content_browser')

    try:
        # Find all pending drafts linked to this conversation
        pending_drafts = ContentDraft.objects.filter(
            conversation=conversation,
            status='pending'
        )

        # Delete pending drafts
        draft_count = pending_drafts.count()
        pending_drafts.delete()

        # Mark conversation as discarded
        conversation.discarded_at = timezone.now()
        conversation.save()

        # Log the action
        logger.info(
            'User %s discarded conversation %s: deleted %d draft(s)',
            request.user.username, conversation_id, draft_count,
        )

        # Success message
        messages.success(
            request,
            f'Conversation discarded. Removed {draft_count} draft(s).'
        )

        return redirect('content_browser')

    except Exception:
        logger.exception('Failed to discard conversation %s', conversation_id)
        messages.error(request, 'Failed to discard conversation. Please try again or contact support.')
        return redirect('chat_index', conversation_id=conversation_id)


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    """
    Delete a conversation permanently.

    This is a simpler action than discard - it just deletes the conversation
    and all its messages. Use this for cleaning up old/test conversations
    from the sidebar.

    Safety: Does NOT delete any ContentDraft objects or reset git commits.
    If the conversation has pending drafts, those remain in the database
    (they'll be orphaned but still accessible via pending approvals).
    """
    from django.contrib import messages

    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Permission check: user must own conversation or be admin
    if conversation.user != request.user and request.user.profile.role != 'admin':
        return HttpResponseForbidden('You do not have permission to delete this conversation.')

    try:
        # Get title for message before deleting
        title = conversation.title

        # Delete the conversation (CASCADE will delete related Message objects)
        conversation.delete()

        messages.success(request, f'Conversation "{title}" deleted successfully.')
        logger.info('User %s deleted conversation %s', request.user.username, conversation_id)

    except Exception:
        logger.exception('Failed to delete conversation %s', conversation_id)
        messages.error(request, 'Failed to delete conversation. Please try again.')

    # Redirect to index (will show next conversation or empty state)
    return redirect('index')


# ---------------------------------------------------------------------------
# Page management views
# ---------------------------------------------------------------------------

@login_required
def page_manager(request):
    """List all CMS-managed static pages."""
    from django.urls import reverse
    profile = request.user.profile
    if profile.role not in ('admin', 'editor'):
        return HttpResponseForbidden()
    from content_schema.schemas import PAGE_TYPES
    pages = [
        {
            "key": key,
            "name": meta["name"],
            "route": meta["route"],
            "url": reverse(meta["editor_url_name"]) if "editor_url_name" in meta else reverse('page_editor', args=[key]),
        }
        for key, meta in PAGE_TYPES.items()
        if profile.can_edit_page(key)
    ]
    return render(request, 'chat/page_manager.html', {
        'pages': pages,
        'profile': profile,
        'active_tab': 'pages',
    })


@login_required
def page_editor(request, page_key):
    """Show sections for a single managed page."""
    profile = request.user.profile
    if not profile.can_edit_page(page_key):
        return HttpResponseForbidden()
    from content_schema.schemas import PAGE_TYPES
    if page_key not in PAGE_TYPES:
        raise Http404
    page_meta = PAGE_TYPES[page_key]
    from .services.page_service import read_page_data
    page_data = read_page_data(page_key)
    return render(request, 'chat/page_editor.html', {
        'page_key': page_key,
        'page_meta': page_meta,
        'page_data': page_data,
        'profile': profile,
        'active_tab': 'pages',
    })


@login_required
def page_section_editor(request, page_key, section_key):
    """Form editor for a single section of a managed page."""
    profile = request.user.profile
    if not profile.can_edit_page(page_key):
        return HttpResponseForbidden()
    from content_schema.schemas import PAGE_TYPES
    if page_key not in PAGE_TYPES:
        raise Http404
    section_meta = PAGE_TYPES[page_key]['sections'].get(section_key)
    if not section_meta:
        raise Http404
    from .services.page_service import read_page_data
    page_data = read_page_data(page_key)
    section_data = page_data.get(section_key, {})
    # Pre-build field list with current values so the template can iterate cleanly
    section_fields = []
    for field_name, field_meta in section_meta['fields'].items():
        raw = section_data.get(field_name, '')
        field_type = field_meta.get('type', 'string')
        if field_type == 'string_array' and isinstance(raw, list):
            value = '\n'.join(raw)
            section_fields.append({
                'name': field_name,
                'label': field_meta.get('label', field_name),
                'type': field_type,
                'admin_only': field_meta.get('admin_only', False),
                'value': value,
            })
        elif field_type == 'object_array':
            value = raw if isinstance(raw, list) else []
            section_fields.append({
                'name': field_name,
                'label': field_meta.get('label', field_name),
                'type': 'object_array',
                'admin_only': field_meta.get('admin_only', False),
                'value': value,
                'item_fields': field_meta.get('item_fields', {}),
                'item_fields_json': json.dumps(field_meta.get('item_fields', {})),
            })
        else:
            value = raw
            section_fields.append({
                'name': field_name,
                'label': field_meta.get('label', field_name),
                'type': field_type,
                'admin_only': field_meta.get('admin_only', False),
                'value': value,
            })
    return render(request, 'chat/page_section_editor.html', {
        'page_key': page_key,
        'section_key': section_key,
        'page_meta': PAGE_TYPES[page_key],
        'section_meta': section_meta,
        'section_fields': section_fields,
        'profile': profile,
        'active_tab': 'pages',
    })


@login_required
@require_http_methods(["POST"])
def page_section_api(request, page_key, section_key):
    """Apply a patch to a page section and commit to git."""
    profile = request.user.profile
    if not profile.can_edit_page(page_key):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    from content_schema.schemas import PAGE_TYPES
    if page_key not in PAGE_TYPES:
        return JsonResponse({'error': 'Unknown page'}, status=404)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Validate admin-only fields
    section_def = PAGE_TYPES[page_key]['sections'].get(section_key, {})
    for field_name, field_meta in section_def.get('fields', {}).items():
        if field_meta.get('admin_only') and field_name in body and profile.role != 'admin':
            return JsonResponse({'error': f'Field {field_name} is admin-only'}, status=403)

    # Coerce string_array fields from newline-delimited textarea strings to lists
    for field_name, field_meta in section_def.get('fields', {}).items():
        if field_meta.get('type') == 'string_array' and field_name in body:
            raw = body[field_name]
            if isinstance(raw, str):
                body[field_name] = [item.strip() for item in raw.split('\n') if item.strip()]

    # Preserve non-schema fields in object_array items by merging with existing data
    from .services.page_service import apply_page_patch, read_page_data
    existing_section = read_page_data(page_key).get(section_key, {})
    for field_name, field_meta in section_def.get('fields', {}).items():
        if field_meta.get('type') == 'object_array' and field_name in body:
            existing_items = existing_section.get(field_name, [])
            new_items = body[field_name]
            if isinstance(new_items, list) and isinstance(existing_items, list):
                merged = []
                for i, new_item in enumerate(new_items):
                    if (i < len(existing_items)
                            and isinstance(existing_items[i], dict)
                            and isinstance(new_item, dict)):
                        merged_item = dict(existing_items[i])
                        merged_item.update(new_item)
                        merged.append(merged_item)
                    else:
                        merged.append(new_item)
                body[field_name] = merged

    try:
        patch = {section_key: body}
        updated = apply_page_patch(page_key, patch)
        return JsonResponse({'status': 'ok', 'data': updated})
    except Exception as e:
        logger.exception("page_section_api error for %s/%s", page_key, section_key)
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Site config views
# ---------------------------------------------------------------------------

def _resolve_dotted(data, dotted_key):
    """Resolve 'stripe_links.founder' to data['stripe_links']['founder']."""
    parts = dotted_key.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _set_dotted(data, dotted_key, value):
    """Set data['stripe_links']['founder'] from 'stripe_links.founder'."""
    parts = dotted_key.split('.')
    current = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _field_group(name):
    """Determine visual group from field name prefix."""
    if name.startswith('stripe_links') or name in ('discord_url', 'action_network_form_id'):
        return 'external_services'
    if name.startswith('founder_scheme'):
        return 'founder_scheme'
    if name.startswith('announcement_bar'):
        return 'announcement_bar'
    return 'other'


@login_required
def site_config_editor(request):
    """Dedicated editor for the flat site-config settings."""
    profile = request.user.profile
    if not profile.can_edit_page('site-config'):
        return HttpResponseForbidden()
    from content_schema.schemas import PAGE_TYPES
    page_meta = PAGE_TYPES['site-config']
    from .services.page_service import read_page_data
    page_data = read_page_data('site-config')

    section_meta = page_meta['sections']['settings']
    fields = []
    for field_name, field_meta in section_meta['fields'].items():
        value = _resolve_dotted(page_data, field_name)
        fields.append({
            'name': field_name,
            'label': field_meta.get('label', field_name),
            'type': field_meta.get('type', 'string'),
            'admin_only': field_meta.get('admin_only', False),
            'value': value if value is not None else '',
            'group': _field_group(field_name),
        })

    from collections import OrderedDict
    grouped = OrderedDict([
        ('external_services', {'label': 'External Services', 'fields': []}),
        ('founder_scheme', {'label': 'Founder Scheme', 'fields': []}),
        ('announcement_bar', {'label': 'Announcement Bar', 'fields': []}),
    ])
    for f in fields:
        group_key = f['group']
        if group_key in grouped:
            grouped[group_key]['fields'].append(f)

    return render(request, 'chat/site_config_editor.html', {
        'page_meta': page_meta,
        'grouped': grouped,
        'profile': profile,
        'active_tab': 'pages',
    })


@login_required
@require_http_methods(["POST"])
def site_config_api(request):
    """Apply a patch to site-config.json and commit to git."""
    profile = request.user.profile
    if not profile.can_edit_page('site-config'):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    from content_schema.schemas import PAGE_TYPES, ADMIN_ONLY_FIELDS
    section_def = PAGE_TYPES['site-config']['sections']['settings']
    admin_fields = ADMIN_ONLY_FIELDS.get('site-config', set())

    # Validate: only accept known field names, check admin-only
    for field_name in body:
        if field_name not in section_def['fields']:
            return JsonResponse({'error': f'Unknown field: {field_name}'}, status=400)
        if field_name in admin_fields and profile.role != 'admin':
            return JsonResponse({'error': f'Field {field_name} is admin-only'}, status=403)

    from .services.page_service import read_page_data, write_page_data
    try:
        current = read_page_data('site-config')

        for field_name, value in body.items():
            field_meta = section_def['fields'][field_name]
            if field_meta.get('type') == 'number':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass
            if field_meta.get('type') == 'boolean':
                if isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes')
            _set_dotted(current, field_name, value)

        write_page_data('site-config', current)
        return JsonResponse({'status': 'ok', 'data': current})
    except Exception as e:
        logger.exception("site_config_api error")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def help_view(request):
    """Help section — editorial guide, roles, and CMS how-tos."""
    profile = request.user.profile
    return render(request, 'chat/help.html', {'profile': profile})
