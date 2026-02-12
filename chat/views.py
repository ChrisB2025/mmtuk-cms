"""
Chat views: conversation UI, message handling, pending approvals.
"""

import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import FileResponse, Http404, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Conversation, Message, ContentDraft, ContentAuditLog
from .services.anthropic_service import (
    build_system_prompt,
    get_conversation_messages,
    call_claude,
    extract_action_block,
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
    read_file_from_repo, delete_file_from_repo,
)
from .services.scraper_service import scrape_url
from .services.image_service import process_image
from .services.pdf_service import extract_pdf, save_pdf_images, get_pdf_image

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
    messages = conv.messages.all()
    profile = request.user.profile

    # Show suggested actions for empty conversations
    suggested_actions = []
    if not messages.exists():
        suggested_actions = _get_suggested_actions(profile)

    return render(request, 'chat/index.html', {
        'conversations': conversations,
        'current_conversation': conv,
        'messages': messages,
        'profile': profile,
        'notifications': [],
        'suggested_actions': suggested_actions,
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
    and re-call Claude with the scraped data.
    """
    url = action_data.get('url', '')
    if not url:
        return 'I tried to scrape a URL but none was provided. Could you paste the URL again?'

    try:
        scraped = scrape_url(url)
    except Exception:
        logger.exception('Scrape failed for %s', url)
        return f'I wasn\'t able to fetch content from that URL. Could you check it\'s correct and try again?'

    # Build a message with the scraped data for Claude
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

    # Re-call Claude with the scraped data
    system_prompt = build_system_prompt(profile)
    all_msgs = get_conversation_messages(conv.messages.all())
    response_text = call_claude(system_prompt, all_msgs)

    return response_text


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
                img_bytes, img_filename = process_image(img_url, slug)
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
                ensure_repo()
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
    and re-call Claude with the content.
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

    # Build a summary for the conversation
    fm_lines = '\n'.join(f'  {k}: {v}' for k, v in fm.items())
    body_preview = item['body'][:6000]
    truncated = '' if len(item['body']) <= 6000 else '\n\n[Body truncated — full content is longer]'

    injected = (
        f'[SYSTEM: Loaded {content_type} "{title}" (slug: {slug})]\n\n'
        f'Frontmatter:\n{fm_lines}\n\n'
        f'Body:\n\n{body_preview}{truncated}'
    )

    Message.objects.create(conversation=conv, role='user', content=injected)

    # Re-call Claude with the loaded content
    system_prompt = build_system_prompt(profile)
    all_msgs = get_conversation_messages(conv.messages.all())
    response_text = call_claude(system_prompt, all_msgs)

    return response_text


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
    Handle a list action: list content and inject into conversation.
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

    # Re-call Claude
    system_prompt = build_system_prompt(profile)
    all_msgs = get_conversation_messages(conv.messages.all())
    response_text = call_claude(system_prompt, all_msgs)

    return response_text


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

    if not uploaded.name.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Only PDF files are accepted.'}, status=400)

    if uploaded.size > 20 * 1024 * 1024:
        return JsonResponse({'error': 'File exceeds the 20MB size limit.'}, status=400)

    file_bytes = uploaded.read()

    # Save a user message for the upload
    Message.objects.create(
        conversation=conv, role='user',
        content=f'[Uploaded PDF: {uploaded.name}]',
    )

    # Update conversation title from first message
    if conv.messages.count() <= 1:
        conv.title = f'PDF: {uploaded.name[:70]}'
        conv.save(update_fields=['title'])

    # Extract text and images
    try:
        result = extract_pdf(file_bytes, uploaded.name)
    except ValueError as exc:
        error_msg = f'Could not process the PDF: {exc}'
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
        meta_lines = f'\nPDF Title: {meta["title"]}\nPDF Author: {meta["author"]}\n'

    injected = (
        f'[SYSTEM: PDF "{result["filename"]}" was uploaded and processed — '
        f'{result["page_count"]} pages]\n'
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

    if action_data:
        action_type = action_data.get('action')
        if action_type == 'create':
            response_text_extra, action_result = _handle_content_action(
                action_data, profile, conv, request.user,
            )
            if action_result and action_result.get('type') != 'error':
                response_text = response_text + '\n\n' + response_text_extra

    # Save assistant response
    Message.objects.create(conversation=conv, role='assistant', content=response_text)

    return JsonResponse({
        'response': response_text,
        'conversation_id': str(conv.id),
        'action_taken': action_result,
    })


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

    try:
        response_text = call_claude(system_prompt, all_msgs)
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

    if action_data:
        action_type = action_data.get('action')

        if action_type == 'scrape':
            # Save Claude's initial response
            Message.objects.create(conversation=conv, role='assistant', content=response_text)

            # Handle scraping and re-call Claude
            response_text = _handle_scrape_action(action_data, profile, conv)
            action_data_2 = extract_action_block(response_text)
            if action_data_2 and action_data_2.get('action') == 'create':
                Message.objects.create(conversation=conv, role='assistant', content=response_text)
                response_text, action_result = _handle_content_action(
                    action_data_2, profile, conv, request.user,
                )

        elif action_type == 'create':
            response_text_extra, action_result = _handle_content_action(
                action_data, profile, conv, request.user,
            )
            if action_result and action_result.get('type') != 'error':
                response_text = response_text + '\n\n' + response_text_extra

        elif action_type == 'read':
            # Save Claude's initial response, then load content and re-call
            Message.objects.create(conversation=conv, role='assistant', content=response_text)
            response_text = _handle_read_action(action_data, profile, conv)
            # Check if the re-call produced an edit action
            action_data_2 = extract_action_block(response_text)
            if action_data_2 and action_data_2.get('action') == 'edit':
                Message.objects.create(conversation=conv, role='assistant', content=response_text)
                response_text, action_result = _handle_edit_action(
                    action_data_2, profile, conv, request.user,
                )

        elif action_type == 'edit':
            response_text_extra, action_result = _handle_edit_action(
                action_data, profile, conv, request.user,
            )
            if action_result and action_result.get('type') != 'error':
                response_text = response_text + '\n\n' + response_text_extra

        elif action_type == 'delete':
            response_text_extra, action_result = _handle_delete_action(
                action_data, profile, conv, request.user,
            )
            if action_result and action_result.get('type') != 'error':
                response_text = response_text + '\n\n' + response_text_extra

        elif action_type == 'list':
            # Save Claude's initial response, then list content and re-call
            Message.objects.create(conversation=conv, role='assistant', content=response_text)
            response_text = _handle_list_action(action_data, profile, conv)

    # Save assistant response
    Message.objects.create(conversation=conv, role='assistant', content=response_text)

    return JsonResponse({
        'response': response_text,
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
    view_mode = request.GET.get('view', 'cards')

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
        item['is_draft'] = fm.get('draft', False)
        item['is_featured'] = fm.get('featured', False)
        item['thumbnail'] = fm.get('thumbnail') or fm.get('image') or ''

    stats = get_content_stats()

    from content_schema.schemas import CONTENT_TYPES
    type_choices = [(k, v['name']) for k, v in CONTENT_TYPES.items()]

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
    if isinstance(d, datetime):
        return d.isoformat()
    return str(d) if d else '0000'


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
            merged_fm[key] = value

    # Get body
    new_body = request.POST.get('body', existing['body'])

    title = merged_fm.get('title') or merged_fm.get('heading') or merged_fm.get('name', 'Untitled')

    # Generate markdown
    markdown, errors = generate_markdown(content_type, merged_fm, new_body)
    if errors:
        # Redirect back with error (simple approach)
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
    """Delete content from the content browser."""
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

        _log_audit(content_type, slug, 'delete', request.user, sha)
        invalidate_cache()

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
    profile = request.user.profile
    if profile.role not in ('admin', 'editor'):
        return HttpResponseForbidden('You do not have permission to publish changes.')

    count = push_to_remote()
    _log_audit('site', 'publish', 'publish', request.user, changes_summary=f'{count} commit(s) pushed')
    logger.info('User %s published %d commit(s) to remote', request.user.username, count)

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
