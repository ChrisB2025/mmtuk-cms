"""
Chat views: conversation UI, message handling, pending approvals.
"""

import json
import logging
import time
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.http import FileResponse, Http404, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .models import Conversation, Message, ContentDraft, ContentAuditLog, DeploymentLog
from .services.anthropic_service import (
    build_system_prompt,
    get_conversation_messages,
    call_claude,
    extract_action_block,
    strip_action_block,
)
from .services.content_service import generate_markdown, get_file_path, get_image_path
from .services.content_reader_service import (
    check_slug_exists, invalidate_cache, list_content, read_content,
    search_content, get_content_stats, list_images,
)
from .services.image_catalog import categorise_images
from .services.git_service import (
    ensure_repo, write_file_to_repo, write_file_to_output,
    commit_locally, push_to_remote, get_unpushed_changes,
    read_file_from_repo, delete_file_from_repo, reset_unpushed_commits,
)
from .services.scraper_service import scrape_url
from .services.image_service import process_image
from .services.pdf_service import extract_pdf, save_pdf_images, get_pdf_image
from .services.docx_service import extract_docx
from .services.astro_validator import validate_against_astro_schema
from .services.railway_service import get_latest_deployment, is_railway_configured
from .services.redirect_service import write_redirects_to_repo, get_redirect_summary

logger = logging.getLogger(__name__)

# --- Suggested actions for empty conversations ---

SUGGESTED_ACTIONS = [
    {
        'id': 'add_news',
        'label': 'Add News Item',
        'message': 'I want to add a news item for the MMTUK site.',
        'action_type': 'send',
        'content_type': 'news',
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_briefing',
        'label': 'Import Briefing from URL',
        'message': 'I want to import a briefing from a Substack URL.',
        'action_type': 'send',
        'content_type': 'briefing',
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_article',
        'label': 'Write New Article',
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
        'id': 'upload_pdf',
        'label': 'Upload a PDF',
        'message': '',
        'action_type': 'upload',
        'content_type': None,
        'admin_only': False,
        'needs_group': False,
    },
    {
        'id': 'add_bio',
        'label': 'Add Team Member Bio',
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
    Handle a create action: validate, generate markdown, handle images,
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

    # Validate against Astro schema (pre-commit validation)
    t0 = time.monotonic()
    is_valid, astro_error = validate_against_astro_schema(content_type, frontmatter)
    logger.info('content_action timing: schema_validation=%.1fs', time.monotonic() - t0)
    if not is_valid:
        error_msg = f'Content does not match Astro schema:\n{astro_error}'
        return error_msg, {'type': 'error', 'message': error_msg}

    # Generate markdown
    markdown, errors = generate_markdown(content_type, frontmatter, body)
    if errors:
        error_msg = 'There were validation errors:\n' + '\n'.join(f'- {e}' for e in errors)
        return error_msg, {'type': 'error', 'message': error_msg}

    # Process images
    image_bytes = None
    image_repo_path = None
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
                    image_repo_path = 'public/' + save_as.lstrip('/')
                else:
                    image_repo_path = get_image_path(content_type, slug)
        else:
            # Image from URL
            img_url = img_info.get('url', '')
            if img_url:
                t1 = time.monotonic()
                img_bytes, img_filename = process_image(img_url, slug)
                logger.info('content_action timing: image_download=%.1fs', time.monotonic() - t1)
                if img_bytes:
                    image_bytes = img_bytes
                    save_as = img_info.get('save_as', '')
                    if save_as:
                        image_repo_path = 'public/' + save_as.lstrip('/')
                    else:
                        image_repo_path = get_image_path(content_type, slug)

    # Check if user can publish directly
    can_publish = profile.can_publish_directly(content_type, local_group)
    file_path = get_file_path(content_type, slug)

    if can_publish:
        # Direct publish via git
        try:
            files_written = []

            if settings.DEBUG:
                write_file_to_output(file_path, markdown)
                if image_bytes and image_repo_path:
                    write_file_to_output(image_repo_path, image_bytes)
                sha = 'debug-mode'
            else:
                t2 = time.monotonic()
                ensure_repo()
                logger.info('content_action timing: ensure_repo=%.1fs', time.monotonic() - t2)
                write_file_to_repo(file_path, markdown)
                files_written.append(file_path)
                if image_bytes and image_repo_path:
                    write_file_to_repo(image_repo_path, image_bytes)
                    files_written.append(image_repo_path)

                commit_msg = f'Add {content_type}: {title} — via MMTUK CMS ({user.username})'
                sha = commit_locally(files_written, commit_msg, user.get_full_name() or user.username)

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
                git_commit_sha=sha,
            )

            _log_audit(content_type, slug, 'create', user, sha)
            invalidate_cache()

            return (
                f'Content published successfully! **{title}** has been committed and will be live shortly after deployment.',
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
                image_path=image_repo_path or '',
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
            image_path=image_repo_path or '',
            status='pending',
        )
        return (
            f'Your {content_type} "{title}" has been saved as a draft and is awaiting approval from an editor or admin.',
            {'type': 'draft_pending', 'draft_id': str(draft.id)},
        )


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
    Handle an edit action: merge frontmatter, regenerate markdown, commit.
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

    # Read existing content
    existing = read_content(content_type, slug)
    if not existing:
        return (
            f'Could not find {content_type} with slug "{slug}" to edit.',
            {'type': 'error', 'message': 'Content not found'},
        )

    # Merge frontmatter (new values override existing)
    merged_fm = dict(existing['frontmatter'])
    merged_fm.update(new_frontmatter)

    # Use new body or keep existing
    body = new_body if new_body is not None else existing['body']

    title = merged_fm.get('title') or merged_fm.get('heading') or merged_fm.get('name', 'Untitled')

    # Validate against Astro schema (pre-commit validation)
    is_valid, astro_error = validate_against_astro_schema(content_type, merged_fm)
    if not is_valid:
        error_msg = f'Content does not match Astro schema:\n{astro_error}'
        return error_msg, {'type': 'error', 'message': error_msg}

    # Generate markdown
    markdown, errors = generate_markdown(content_type, merged_fm, body)
    if errors:
        error_msg = 'Validation errors:\n' + '\n'.join(f'- {e}' for e in errors)
        return error_msg, {'type': 'error', 'message': error_msg}

    # Process images if provided
    image_bytes = None
    image_repo_path = None
    if images:
        img_info = images[0]
        img_url = img_info.get('url', '')
        if img_url:
            img_bytes, img_filename = process_image(img_url, slug)
            if img_bytes:
                image_bytes = img_bytes
                save_as = img_info.get('save_as', '')
                if save_as:
                    image_repo_path = 'public/' + save_as.lstrip('/')
                else:
                    image_repo_path = get_image_path(content_type, slug)

    file_path = get_file_path(content_type, slug)

    try:
        files_written = []

        if settings.DEBUG:
            write_file_to_output(file_path, markdown)
            if image_bytes and image_repo_path:
                write_file_to_output(image_repo_path, image_bytes)
            sha = 'debug-mode'
        else:
            ensure_repo()
            write_file_to_repo(file_path, markdown)
            files_written.append(file_path)
            if image_bytes and image_repo_path:
                write_file_to_repo(image_repo_path, image_bytes)
                files_written.append(image_repo_path)

            commit_msg = f'Edit {content_type}: {title} — via MMTUK CMS ({user.username})'
            sha = commit_locally(files_written, commit_msg, user.get_full_name() or user.username)

        # Record the edit
        ContentDraft.objects.create(
            conversation=conv,
            created_by=user,
            content_type=content_type,
            title=title,
            slug=slug,
            frontmatter_json=merged_fm,
            body_markdown=body,
            status='published',
            git_commit_sha=sha,
        )

        # Log to audit trail
        _log_audit(content_type, slug, 'edit', user, sha)

        invalidate_cache()

        return (
            f'Content updated successfully! **{title}** has been committed and will be live shortly.',
            {'type': 'content_edited', 'title': title, 'content_type': content_type},
        )

    except Exception:
        logger.exception('Failed to edit content')
        return (
            f'There was an error saving the edits to "{title}". Please try again.',
            {'type': 'error', 'message': 'Failed to save edits'},
        )


def _handle_delete_action(action_data, profile, conv, user):
    """
    Handle a delete action: remove file from repo and commit.
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

    # Verify content exists
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

    file_path = get_file_path(content_type, slug)

    try:
        if settings.DEBUG:
            logger.info('DEBUG mode: would delete %s', file_path)
            sha = 'debug-mode'
        else:
            ensure_repo()
            deleted = delete_file_from_repo(file_path)
            if not deleted:
                return (
                    f'The file for "{title}" was not found in the repo.',
                    {'type': 'error', 'message': 'File not found in repo'},
                )

            commit_msg = f'Delete {content_type}: {title} — via MMTUK CMS ({user.username})'
            sha = commit_locally([file_path], commit_msg, user.get_full_name() or user.username)

        # Log to audit trail
        _log_audit(content_type, slug, 'delete', user, sha)

        invalidate_cache()

        return (
            f'**{title}** ({content_type}) has been deleted and the change committed.',
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


@login_required
@require_POST
def send_message(request, conversation_id):
    """Handle a chat message from the user."""
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

    # Build messages and call Claude
    system_prompt = build_system_prompt(profile)
    all_msgs = get_conversation_messages(conv.messages.all())
    logger.info('send_message: conv=%s, history_len=%s, msg_preview=%.80r', conv.id, len(all_msgs), user_message)

    try:
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

    # Generate the markdown preview
    markdown_preview, _ = generate_markdown(draft.content_type, draft.frontmatter_json, draft.body_markdown)

    return render(request, 'chat/pending_detail.html', {
        'draft': draft,
        'markdown_preview': markdown_preview or '',
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

    # Generate markdown
    markdown, errors = generate_markdown(draft.content_type, draft.frontmatter_json, draft.body_markdown)
    if errors:
        return JsonResponse({'error': 'Validation errors: ' + '; '.join(errors)}, status=400)

    file_path = get_file_path(draft.content_type, draft.slug)
    title = draft.title

    try:
        files_written = []

        if settings.DEBUG:
            write_file_to_output(file_path, markdown)
            sha = 'debug-mode'
        else:
            ensure_repo()
            write_file_to_repo(file_path, markdown)
            files_written.append(file_path)

            # Write image if present
            if draft.image_data and draft.image_path:
                write_file_to_repo(draft.image_path, bytes(draft.image_data))
                files_written.append(draft.image_path)

            commit_msg = f'Add {draft.content_type}: {title} — via MMTUK CMS (approved by {request.user.username})'
            sha = commit_locally(
                files_written, commit_msg,
                request.user.get_full_name() or request.user.username,
            )

        draft.status = 'approved'
        draft.reviewer = request.user
        draft.reviewed_at = timezone.now()
        draft.git_commit_sha = sha
        draft.save()

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
        item['date'] = fm.get('pubDate') or fm.get('date') or ''
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

    from content_schema.schemas import CONTENT_TYPES
    type_choices = [(k, v['name']) for k, v in CONTENT_TYPES.items()]

    # Get latest deployment status for dashboard widget
    latest_deployment = DeploymentLog.objects.order_by('-started_at').first()

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
        'latest_deployment': latest_deployment,
    })


def _sort_date(item):
    """Extract a sortable date string from a content item."""
    fm = item.get('frontmatter', {})
    d = fm.get('pubDate') or fm.get('date') or ''
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

    # Update frontmatter
    frontmatter = item['frontmatter']
    frontmatter['archived'] = False

    # Generate markdown
    from chat.services.content_service import generate_markdown
    markdown_content = generate_markdown(frontmatter, item['body'])

    # Get file path
    from content_schema.schemas import CONTENT_TYPES
    schema = CONTENT_TYPES[content_type]
    directory = schema['directory']
    filename_pattern = schema['filename_pattern']
    filename = filename_pattern.format(slug=slug)
    file_path = f'{directory}{filename}'

    # Write to repo
    from chat.services.git_service import write_file_to_repo, commit_locally
    write_file_to_repo(file_path, markdown_content)

    # Commit
    commit_locally(
        files=[file_path],
        message=f'chore: Unarchive event "{frontmatter.get("title", slug)}"',
        author_name=f'{request.user.username} (via CMS)'
    )

    # Invalidate cache
    from chat.services.content_reader_service import invalidate_cache
    invalidate_cache()

    # Log audit
    from chat.models import ContentAuditLog
    ContentAuditLog.objects.create(
        user=request.user,
        action='unarchive',
        content_type=content_type,
        slug=slug,
        details=f'Unarchived event: {frontmatter.get("title", slug)}'
    )

    messages.success(request, f'✓ Event unarchived: {frontmatter.get("title", slug)}')
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

    from content_schema.schemas import CONTENT_TYPES
    schema = CONTENT_TYPES.get(content_type, {})
    title = (
        item['frontmatter'].get('title')
        or item['frontmatter'].get('heading')
        or item['frontmatter'].get('name')
        or 'Untitled'
    )

    # Build site URL
    route = schema.get('route', '')
    site_url = ''
    if route and '{slug}' in route:
        site_url = 'https://mmtuk.org' + route.format(slug=slug)

    # Get audit log entries for this item (if model exists)
    audit_entries = []
    if ContentAuditLog is not None:
        try:
            audit_entries = list(ContentAuditLog.objects.filter(
                content_type=content_type, slug=slug,
            ).order_by('-created_at')[:20])
        except Exception:
            pass

    return render(request, 'chat/content_detail.html', {
        'conversations': conversations,
        'item': item,
        'content_type': content_type,
        'slug': slug,
        'title': title,
        'schema': schema,
        'site_url': site_url,
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

    # Collect frontmatter from form fields (prefixed with fm_)
    from content_schema.schemas import CONTENT_TYPES as CT_SCHEMAS
    schema = CT_SCHEMAS.get(content_type, {})
    required_fields = set(schema.get('required_fields', []))

    merged_fm = dict(existing['frontmatter'])
    for key in list(existing['frontmatter'].keys()):
        form_key = f'fm_{key}'
        if form_key in request.POST:
            value = request.POST[form_key]
            # Convert string booleans
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            # Convert empty optional fields to None (sanitize_frontmatter will strip them)
            elif value == '' and key not in required_fields:
                value = None
            merged_fm[key] = value

    # Get body
    new_body = request.POST.get('body', existing['body'])

    title = merged_fm.get('title') or merged_fm.get('heading') or merged_fm.get('name', 'Untitled')

    # Validate against Astro schema (pre-commit validation)
    is_valid, astro_error = validate_against_astro_schema(content_type, merged_fm)
    if not is_valid:
        # Show error via Django messages
        from django.contrib import messages
        messages.error(request, f'Validation error: {astro_error}')
        return redirect('content_detail', content_type=content_type, slug=slug)

    # Generate markdown
    markdown, errors = generate_markdown(content_type, merged_fm, new_body)
    if errors:
        # Redirect back with error (simple approach)
        from django.contrib import messages
        messages.error(request, f'Validation errors: {"; ".join(errors)}')
        return redirect('content_detail', content_type=content_type, slug=slug)

    file_path = get_file_path(content_type, slug)

    try:
        files_written = []

        if settings.DEBUG:
            write_file_to_output(file_path, markdown)
            sha = 'debug-mode'
        else:
            ensure_repo()
            write_file_to_repo(file_path, markdown)
            files_written.append(file_path)

            commit_msg = f'Quick edit {content_type}: {title} — via MMTUK CMS ({request.user.username})'
            sha = commit_locally(files_written, commit_msg, request.user.get_full_name() or request.user.username)

        _log_audit(content_type, slug, 'edit', request.user, sha)
        invalidate_cache()

    except Exception:
        logger.exception('Quick edit failed')

    return redirect('content_detail', content_type=content_type, slug=slug)


@login_required
@require_POST
def delete_content(request, content_type, slug):
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

    file_path = get_file_path(content_type, slug)

    try:
        if settings.DEBUG:
            sha = 'debug-mode'
        else:
            ensure_repo()
            deleted = delete_file_from_repo(file_path)
            if not deleted:
                return redirect('content_browser')

            commit_msg = f'Delete {content_type}: {title} — via MMTUK CMS ({request.user.username})'
            sha = commit_locally([file_path], commit_msg, request.user.get_full_name() or request.user.username)

        # Log deletion with redirect tracking
        audit_log = ContentAuditLog.objects.create(
            content_type=content_type,
            slug=slug,
            action='delete',
            user=request.user,
            git_commit_sha=sha,
            changes_summary=f'Deleted: {title}',
            deleted_at=timezone.now(),
            redirect_target=redirect_target,
        )

        invalidate_cache()

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

    # Can upload: admin, editor, group_lead
    can_upload = profile.role in ('admin', 'editor', 'group_lead')

    # Build hierarchical section data (unless flat view requested)
    sections = []
    if view_mode != 'flat':
        sections = categorise_images(images)

    return render(request, 'chat/media_library.html', {
        'conversations': conversations,
        'images': images,
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
        filename = 'upload.png'

    image_bytes = uploaded.read()

    # Convert to PNG if needed (skip SVG)
    if uploaded.content_type != 'image/svg+xml' and not filename.lower().endswith('.png'):
        from .services.image_service import convert_to_png
        try:
            image_bytes = convert_to_png(image_bytes)
            filename = filename.rsplit('.', 1)[0] + '.png'
        except Exception:
            pass  # Keep original format

    repo_path = f'public/{save_dir.strip("/")}/{filename}'

    try:
        if settings.DEBUG:
            write_file_to_output(repo_path, image_bytes)
            sha = 'debug-mode'
        else:
            ensure_repo()
            write_file_to_repo(repo_path, image_bytes)
            commit_msg = f'Upload image: {filename} — via MMTUK CMS ({request.user.username})'
            sha = commit_locally([repo_path], commit_msg, request.user.get_full_name() or request.user.username)

        invalidate_cache()

        # Web path for use in frontmatter
        web_path = '/' + repo_path.replace('public/', '', 1)

        return JsonResponse({
            'success': True,
            'path': repo_path,
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

    rel_path = 'public' + web_path  # e.g. public/images/news/foo.png
    filename = rel_path.rsplit('/', 1)[-1]

    try:
        if settings.DEBUG:
            import pathlib
            full = pathlib.Path(settings.OUTPUT_DIR) / rel_path
            if full.exists():
                full.unlink()
        else:
            from .services.git_service import delete_file_from_repo, commit_locally
            if not delete_file_from_repo(rel_path):
                return JsonResponse({'error': 'Image not found'}, status=404)
            commit_msg = f'Delete image: {filename} — via MMTUK CMS ({request.user.username})'
            commit_locally([rel_path], commit_msg, request.user.get_full_name() or request.user.username)

        invalidate_cache()
        return JsonResponse({'success': True})

    except Exception:
        logger.exception('Image delete failed for %s', web_path)
        return JsonResponse({'error': 'Failed to delete image.'}, status=500)


@login_required
def images_api(request):
    """Return a flat JSON list of all images for the image picker."""
    images = list_images()
    return JsonResponse({'images': [
        {'web_path': img['web_path'], 'filename': img['filename']}
        for img in images
    ]})


# --- Repo image serving ---

@login_required
def repo_image(request, image_path):
    """Serve an image from the repo clone's public/ directory."""
    import mimetypes
    from pathlib import Path

    # Prevent path traversal
    clean = Path(image_path).as_posix()
    if '..' in clean:
        raise Http404

    clone_dir = Path(settings.REPO_CLONE_DIR)
    full_path = clone_dir / 'public' / clean

    if not full_path.exists() or not full_path.is_file():
        # Fallback to output dir in DEBUG mode
        if settings.DEBUG:
            full_path = Path(settings.OUTPUT_DIR) / 'public' / clean
        if not full_path.exists() or not full_path.is_file():
            raise Http404

    content_type, _ = mimetypes.guess_type(str(full_path))
    return FileResponse(open(full_path, 'rb'), content_type=content_type or 'application/octet-stream')


# --- Featured toggle API ---

@login_required
@require_POST
def toggle_featured(request, content_type, slug):
    """Toggle the 'featured' field on a content item."""
    profile = request.user.profile
    if not profile.can_edit(content_type):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    existing = read_content(content_type, slug)
    if not existing:
        return JsonResponse({'error': 'Content not found'}, status=404)

    fm = dict(existing['frontmatter'])
    fm['featured'] = not fm.get('featured', False)

    title = fm.get('title') or fm.get('heading') or fm.get('name', 'Untitled')

    markdown, errors = generate_markdown(content_type, fm, existing['body'])
    if errors:
        return JsonResponse({'error': '; '.join(errors)}, status=400)

    file_path = get_file_path(content_type, slug)

    try:
        if settings.DEBUG:
            write_file_to_output(file_path, markdown)
            sha = 'debug-mode'
        else:
            ensure_repo()
            write_file_to_repo(file_path, markdown)
            action_word = 'Set' if fm['featured'] else 'Unset'
            commit_msg = f'{action_word} featured on {content_type}: {title} — via MMTUK CMS ({request.user.username})'
            sha = commit_locally([file_path], commit_msg, request.user.get_full_name() or request.user.username)

        _log_audit(content_type, slug, 'edit', request.user, sha, f'featured={fm["featured"]}')
        invalidate_cache()

        return JsonResponse({'success': True, 'featured': fm['featured']})

    except Exception:
        logger.exception('Toggle featured failed')
        return JsonResponse({'error': 'Failed to update.'}, status=500)


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
            existing = read_content(ct, slug)
            if not existing:
                results['errors'] += 1
                continue

            title = (
                existing['frontmatter'].get('title')
                or existing['frontmatter'].get('heading')
                or existing['frontmatter'].get('name')
                or 'Untitled'
            )
            file_path = get_file_path(ct, slug)

            try:
                if settings.DEBUG:
                    logger.info('DEBUG mode: would delete %s', file_path)
                else:
                    ensure_repo()
                    delete_file_from_repo(file_path)
                    commit_locally(
                        [file_path],
                        f'Bulk delete {ct}: {title} — via MMTUK CMS ({request.user.username})',
                        request.user.get_full_name() or request.user.username,
                    )

                _log_audit(ct, slug, 'delete', request.user)
                results['success'] += 1
            except Exception:
                logger.exception('Bulk delete failed for %s/%s', ct, slug)
                results['errors'] += 1

        elif action == 'set_draft':
            existing = read_content(ct, slug)
            if not existing:
                results['errors'] += 1
                continue

            fm = dict(existing['frontmatter'])
            fm['draft'] = True
            markdown, errors = generate_markdown(ct, fm, existing['body'])
            if errors:
                results['errors'] += 1
                continue

            file_path = get_file_path(ct, slug)
            try:
                if settings.DEBUG:
                    write_file_to_output(file_path, markdown)
                else:
                    ensure_repo()
                    write_file_to_repo(file_path, markdown)
                    commit_locally(
                        [file_path],
                        f'Set draft on {ct}: {slug} — via MMTUK CMS ({request.user.username})',
                        request.user.get_full_name() or request.user.username,
                    )
                results['success'] += 1
            except Exception:
                results['errors'] += 1

        elif action == 'unset_draft':
            existing = read_content(ct, slug)
            if not existing:
                results['errors'] += 1
                continue

            fm = dict(existing['frontmatter'])
            fm['draft'] = False
            markdown, errors = generate_markdown(ct, fm, existing['body'])
            if errors:
                results['errors'] += 1
                continue

            file_path = get_file_path(ct, slug)
            try:
                if settings.DEBUG:
                    write_file_to_output(file_path, markdown)
                else:
                    ensure_repo()
                    write_file_to_repo(file_path, markdown)
                    commit_locally(
                        [file_path],
                        f'Unset draft on {ct}: {slug} — via MMTUK CMS ({request.user.username})',
                        request.user.get_full_name() or request.user.username,
                    )
                results['success'] += 1
            except Exception:
                results['errors'] += 1

    invalidate_cache()
    return JsonResponse(results)


# --- Review & Publish ---

@login_required
def review_changes(request):
    """Review all pending changes before publishing."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]

    unpushed = get_unpushed_changes()

    # Enrich each commit with content_type + slug from audit log so we can link to the item
    for commit in unpushed:
        log = ContentAuditLog.objects.filter(
            git_commit_sha__startswith=commit['sha']
        ).first()
        if log:
            commit['content_type'] = log.content_type
            commit['slug'] = log.slug

    pending_drafts = ContentDraft.objects.filter(status='pending')

    # Scope for group leads
    if profile.role == 'group_lead' and profile.local_group:
        pending_drafts = pending_drafts.filter(
            frontmatter_json__localGroup=profile.local_group
        )

    recent_audit = ContentAuditLog.objects.select_related('user')[:20]

    return render(request, 'chat/review_changes.html', {
        'unpushed': unpushed,
        'unpushed_count': len(unpushed),
        'pending_drafts': pending_drafts,
        'pending_count': pending_drafts.count(),
        'recent_audit': recent_audit,
        'can_publish': profile.role in ('admin', 'editor'),
        'conversations': conversations,
        'profile': profile,
    })


# --- Publish (batched push) ---

@login_required
@require_POST
def publish_changes(request):
    """Push all unpushed local commits to the remote (triggers site deploy)."""
    from django.contrib import messages

    profile = request.user.profile
    if profile.role not in ('admin', 'editor'):
        return HttpResponseForbidden('You do not have permission to publish changes.')

    # Generate redirects config for deleted content (SEO preservation)
    try:
        redirect_summary = get_redirect_summary()
        if redirect_summary['total_count'] > 0:
            logger.info(f'Generating {redirect_summary["total_count"]} redirect(s) before publish')
            write_redirects_to_repo()
            # Commit the redirects file
            from .services.git_service import commit_locally
            commit_locally(
                ['redirects.config.mjs'],
                f'Update redirects: {redirect_summary["total_count"]} redirect(s) — via MMTUK CMS',
                'MMTUK CMS'
            )
    except Exception as e:
        # Fail open - don't block publish if redirect generation fails
        logger.exception(f'Failed to generate redirects: {e}')
        messages.warning(request, 'Warning: Could not generate redirects config.')

    # Get unpushed commits before push (for Railway tracking)
    unpushed = get_unpushed_changes()
    latest_commit_sha = unpushed[0]['sha'] if unpushed else ''

    count = push_to_remote()
    _log_audit('site', 'publish', 'publish', request.user, changes_summary=f'{count} commit(s) pushed')
    logger.info('User %s published %d commit(s) to remote', request.user.username, count)

    # Track Railway deployment if configured
    if is_railway_configured() and count > 0:
        try:
            # Wait a moment for Railway to detect the push and create deployment
            import time
            time.sleep(2)

            deployment_id = get_latest_deployment()
            if deployment_id:
                DeploymentLog.objects.create(
                    deployment_id=deployment_id,
                    commit_sha=latest_commit_sha,
                    triggered_by=request.user,
                    status='pending',
                )
                messages.success(
                    request,
                    f'{count} commit(s) published. Railway deployment {deployment_id[:8]}... is being monitored.'
                )
                logger.info('Created deployment log for %s', deployment_id[:8])
            else:
                messages.warning(
                    request,
                    f'{count} commit(s) published, but could not fetch Railway deployment ID.'
                )
        except Exception as e:
            # Fail open - don't block publish if Railway tracking fails
            logger.exception('Failed to create deployment log: %s', e)
            messages.success(request, f'{count} commit(s) published successfully.')
    else:
        messages.success(request, f'{count} commit(s) published successfully.')

    # Redirect back to referring page, or content browser
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        return redirect(referer)
    return redirect('content_browser')


@login_required
def pending_publish(request):
    """JSON API returning the count and details of unpushed commits."""
    changes = get_unpushed_changes()
    return JsonResponse({
        'count': len(changes),
        'commits': changes,
    })


# --- Redirect Management (SEO) ---

@login_required
@permission_required('accounts.can_approve_content', raise_exception=True)
def redirect_management(request):
    """View and manage redirects for deleted content (admin/editor only)."""
    profile = request.user.profile
    conversations = Conversation.objects.filter(user=request.user)[:20]

    # Get redirect summary
    summary = get_redirect_summary()

    # Count grouped targets
    grouped_count = len(summary['grouped'])

    # Get deleted content with no redirect (intentional 404s)
    intentional_404s = ContentAuditLog.objects.filter(
        action='delete',
        deleted_at__isnull=False,
        redirect_target='',
    ).select_related('user').order_by('-deleted_at')[:50]

    return render(request, 'chat/redirect_management.html', {
        'summary': summary,
        'grouped_count': grouped_count,
        'deleted_no_redirect': intentional_404s.count(),
        'intentional_404s': intentional_404s,
        'conversations': conversations,
        'profile': profile,
    })


@login_required
@permission_required('accounts.can_approve_content', raise_exception=True)
@require_POST
def edit_redirect(request):
    """Edit a redirect target for deleted content."""
    from django.contrib import messages
    from .services.redirect_service import validate_redirect_target

    source_path = request.POST.get('source_path', '').strip()
    redirect_target = request.POST.get('redirect_target', '').strip()

    if not source_path:
        messages.error(request, 'Invalid source path.')
        return redirect('redirect_management')

    # Validate redirect target
    is_valid, error_message = validate_redirect_target(redirect_target)
    if not is_valid:
        messages.error(request, f'Invalid redirect target: {error_message}')
        return redirect('redirect_management')

    # Find the ContentAuditLog entry
    # Parse source_path to extract content_type and slug
    # Format: /articles/slug or /news/slug
    parts = source_path.strip('/').split('/')
    if len(parts) != 2:
        messages.error(request, 'Invalid source path format.')
        return redirect('redirect_management')

    # Map URL paths back to content types
    path_to_type = {
        'articles': 'article',
        'news': 'news',
        'briefings': 'briefing',
        'local-events': 'local_event',
        'local-news': 'local_news',
        'about': 'bio',
        'ecosystem': 'ecosystem',
        'local-groups': 'local_group',
    }

    content_type = path_to_type.get(parts[0])
    slug = parts[1]

    if not content_type:
        messages.error(request, f'Unknown content type: {parts[0]}')
        return redirect('redirect_management')

    # Update the most recent delete log for this content
    audit_log = ContentAuditLog.objects.filter(
        action='delete',
        content_type=content_type,
        slug=slug,
        deleted_at__isnull=False,
    ).order_by('-deleted_at').first()

    if not audit_log:
        messages.error(request, 'Could not find deleted content record.')
        return redirect('redirect_management')

    audit_log.redirect_target = redirect_target
    audit_log.save()

    if redirect_target:
        messages.success(
            request,
            f'Updated redirect: {source_path} → {redirect_target}'
        )
    else:
        messages.success(
            request,
            f'Removed redirect for {source_path} (will return 404)'
        )

    return redirect('redirect_management')


@login_required
@permission_required('accounts.can_approve_content', raise_exception=True)
@require_POST
def remove_redirect(request):
    """Remove a redirect (set target to empty, content will 404)."""
    from django.contrib import messages

    source_path = request.POST.get('source_path', '').strip()

    if not source_path:
        messages.error(request, 'Invalid source path.')
        return redirect('redirect_management')

    # Parse source_path to extract content_type and slug
    parts = source_path.strip('/').split('/')
    if len(parts) != 2:
        messages.error(request, 'Invalid source path format.')
        return redirect('redirect_management')

    path_to_type = {
        'articles': 'article',
        'news': 'news',
        'briefings': 'briefing',
        'local-events': 'local_event',
        'local-news': 'local_news',
        'about': 'bio',
        'ecosystem': 'ecosystem',
        'local-groups': 'local_group',
    }

    content_type = path_to_type.get(parts[0])
    slug = parts[1]

    if not content_type:
        messages.error(request, f'Unknown content type: {parts[0]}')
        return redirect('redirect_management')

    # Update audit log to remove redirect
    audit_log = ContentAuditLog.objects.filter(
        action='delete',
        content_type=content_type,
        slug=slug,
        deleted_at__isnull=False,
    ).order_by('-deleted_at').first()

    if not audit_log:
        messages.error(request, 'Could not find deleted content record.')
        return redirect('redirect_management')

    audit_log.redirect_target = ''
    audit_log.save()

    messages.success(
        request,
        f'Removed redirect for {source_path} (will return 404)'
    )

    return redirect('redirect_management')


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

        # Collect commit SHAs from drafts that have them
        commit_shas = [
            draft.git_commit_sha
            for draft in pending_drafts
            if draft.git_commit_sha and draft.git_commit_sha != 'debug-no-push'
        ]

        # Reset unpushed commits (preserves file changes via soft reset)
        reset_count = 0
        if commit_shas:
            try:
                reset_count = reset_unpushed_commits(commit_shas)
            except ValueError as e:
                # Commits are already pushed - can't discard
                messages.error(
                    request,
                    f'Cannot discard: some changes have already been published. {str(e)}'
                )
                return redirect('chat_index', conversation_id=conversation_id)

        # Delete pending drafts
        draft_count = pending_drafts.count()
        pending_drafts.delete()

        # Mark conversation as discarded
        conversation.discarded_at = timezone.now()
        conversation.save()

        # Log the action
        logger.info(
            'User %s discarded conversation %s: deleted %d draft(s), reset %d commit(s)',
            request.user.username, conversation_id, draft_count, reset_count
        )

        # Success message
        messages.success(
            request,
            f'Conversation discarded. Removed {draft_count} draft(s) and reset {reset_count} unpublished commit(s).'
        )

        invalidate_cache()
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
