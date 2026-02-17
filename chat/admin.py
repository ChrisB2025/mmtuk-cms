from django.contrib import admin
from .models import Conversation, Message, ContentDraft, ContentAuditLog


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['id', 'role', 'content', 'created_at']
    can_delete = False
    max_num = 0
    show_change_link = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'created_at', 'updated_at']
    list_filter = ['user']
    search_fields = ['title', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [MessageInline]
    actions = ['delete_selected_conversations']

    @admin.action(description='Delete selected conversations')
    def delete_selected_conversations(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} conversation(s) deleted successfully.')

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(ContentDraft)
class ContentDraftAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'content_type']
    search_fields = ['title', 'slug', 'created_by__username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'created_at', 'created_by']


@admin.register(ContentAuditLog)
class ContentAuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'content_type', 'slug', 'user', 'created_at']
    list_filter = ['action', 'content_type']
    search_fields = ['slug', 'user__username']
    ordering = ['-created_at']
    readonly_fields = ['id', 'action', 'content_type', 'slug', 'user',
                       'created_at', 'git_commit_sha']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
