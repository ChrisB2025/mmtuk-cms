from django.contrib import admin

from .models import (
    Article, Briefing, News, Bio, EcosystemEntry,
    LocalGroup, LocalEvent, LocalNews,
)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'pub_date', 'status']
    list_filter = ['category', 'layout', 'status', 'featured']
    search_fields = ['title', 'slug', 'author', 'summary']
    prepopulated_fields = {'slug': ('title',)}


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
        if not obj.image and obj.link:
            self._fetch_event_image(obj)

    def _fetch_event_image(self, obj):
        import logging
        from chat.services.scraper_service import scrape_general_url
        from chat.services.image_service import process_image
        from chat.services.content_service import get_image_save_path
        logger = logging.getLogger(__name__)
        try:
            data = scrape_general_url(obj.link)
            image_url = data.get('image_url', '')
            if not image_url:
                logger.info('LocalEvent admin: no og:image found for %s', obj.link)
                return
            img_bytes, _ = process_image(image_url, obj.slug)
            if not img_bytes:
                logger.warning('LocalEvent admin: image processing failed for %s', image_url)
                return
            abs_path, web_path = get_image_save_path('local_event', obj.slug)
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            with open(abs_path, 'wb') as f:
                f.write(img_bytes)
            obj.image = web_path
            obj.save(update_fields=['image'])
            logger.info('LocalEvent admin: saved image %s for %s', web_path, obj.slug)
        except Exception:
            logger.exception('LocalEvent admin: image auto-fetch failed for %s', obj.link)


@admin.register(LocalNews)
class LocalNewsAdmin(admin.ModelAdmin):
    list_display = ['heading', 'local_group', 'date', 'status']
    list_filter = ['status', 'local_group']
    search_fields = ['heading', 'slug', 'text']
    prepopulated_fields = {'slug': ('heading',)}
