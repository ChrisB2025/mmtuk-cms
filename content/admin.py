from django.contrib import admin

from .models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'pub_date', 'education_order', 'status']
    list_filter = ['category', 'layout', 'status', 'featured']
    list_editable = ['education_order']
    search_fields = ['title', 'slug', 'author', 'summary']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'category', 'layout', 'author', 'author_title', 'pub_date')}),
        ('Content', {'fields': ('summary', 'accordion_text', 'body')}),
        ('Display', {'fields': ('education_order', 'read_time', 'thumbnail', 'main_image', 'featured', 'color', 'sector', 'status')}),
    )


@admin.register(Briefing)
class BriefingAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'pub_date', 'status', 'draft']
    list_filter = ['status', 'featured', 'draft']
    search_fields = ['title', 'slug', 'author', 'summary']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'date', 'status']
    list_filter = ['category', 'status']
    search_fields = ['title', 'slug', 'summary']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Bio)
class BioAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'advisory_board', 'status']
    list_filter = ['advisory_board', 'status']
    search_fields = ['name', 'slug', 'role']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(EcosystemEntry)
class EcosystemEntryAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'activity_status', 'status']
    list_filter = ['activity_status', 'status', 'country']
    search_fields = ['name', 'slug', 'summary']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LocalGroup)
class LocalGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'title', 'active', 'status']
    list_filter = ['active', 'status']
    search_fields = ['name', 'slug', 'title']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(LocalEvent)
class LocalEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'local_group', 'date', 'tag', 'archived', 'status']
    list_filter = ['archived', 'partner_event', 'status', 'local_group']
    search_fields = ['title', 'slug', 'location', 'description']
    prepopulated_fields = {'slug': ('title',)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.link:
            from chat.views import _ensure_event_image
            _ensure_event_image(obj)


@admin.register(LocalNews)
class LocalNewsAdmin(admin.ModelAdmin):
    list_display = ['heading', 'local_group', 'date', 'status']
    list_filter = ['status', 'local_group']
    search_fields = ['heading', 'slug', 'text']
    prepopulated_fields = {'slug': ('heading',)}
