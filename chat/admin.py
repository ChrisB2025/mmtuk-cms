from django.contrib import admin
from .models import Conversation, Message, ContentDraft, ContentAuditLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'created_at', 'updated_at']
    list_filter = ['user']
    readonly_fields = ['id']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['role', 'short_content', 'conversation', 'created_at']
    list_filter = ['role']
    readonly_fields = ['id']

    def short_content(self, obj):
        return obj.content[:80]
    short_content.short_description = 'Content'


@admin.register(ContentDraft)
class ContentDraftAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'content_type']
    readonly_fields = ['id']


@admin.register(ContentAuditLog)
class ContentAuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'content_type', 'slug', 'user', 'created_at']
    list_filter = ['action', 'content_type']
    readonly_fields = ['id']
