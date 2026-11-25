from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Advertisement,
    Article,
    BreakingNews,
    Category,
    Comment,
    ContactMessage,
    Locality,
    NewsletterSubscriber,
    NotificationSubscription,
    PageView,
    Profile,
    Tag,
    Video,
)
from .utils import sanitize_editorial_html


admin.site.site_header = "KERICHO DAILY — Newsroom"
admin.site.site_title = "Kericho Daily CMS"
admin.site.index_title = "Editorial Control Centre"


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ["role", "is_journalist", "bio", "phone", "x_profile", "facebook", "show_on_team_page"]


class KerichoUserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ("username", "email", "first_name", "last_name", "role_display", "is_staff")
    list_filter = ("is_staff", "is_superuser", "profile__role", "is_active")

    @admin.display(description="Newsroom role")
    def role_display(self, obj):
        return getattr(getattr(obj, "profile", None), "role", "—")


admin.site.unregister(User)
admin.site.register(User, KerichoUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "role", "is_journalist", "show_on_team_page")
    list_filter = ("role", "is_journalist", "show_on_team_page")
    search_fields = ("user__username", "user__first_name", "user__last_name", "bio")
    autocomplete_search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "show_in_nav", "order", "article_count")
    list_editable = ("show_in_nav", "order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")

    @admin.display(description="Published stories")
    def article_count(self, obj):
        return obj.article_count


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "article_count")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)

    @admin.display(description="Stories")
    def article_count(self, obj):
        return obj.articles.count()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "author", "status", "published_at",
        "views_count", "is_featured", "is_breaking", "is_sample",
    )
    list_filter = ("status", "category", "is_featured", "is_breaking", "is_sponsored", "is_sample", "author__role")
    search_fields = ("title", "subtitle", "excerpt", "body", "slug", "seo_title")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("localities", "tags")
    autocomplete_fields = ("author", "category")
    date_hierarchy = "published_at"
    readonly_fields = ("views_count", "reading_time", "created_at", "updated_at", "image_preview")
    fieldsets = (
        ("Editorial", {"fields": ("title", "slug", "subtitle", "excerpt", "body")}),
        ("Classification", {"fields": ("category", "localities", "tags", "author", "status", "published_at")}),
        ("Media", {"fields": ("featured_image", "featured_image_url", "image_preview", "image_caption", "image_credit")}),
        ("Flags", {"fields": ("is_featured", "is_breaking", "is_sponsored", "sponsor_name", "allow_comments", "is_sample")}),
        ("Source", {"classes": ("collapse",), "fields": ("source_name", "source_url")}),
        ("SEO", {"classes": ("collapse",), "fields": ("seo_title", "seo_description", "canonical_url", "focus_keyword")}),
        ("Metrics", {"classes": ("collapse",), "fields": ("views_count", "reading_time", "created_at", "updated_at")}),
    )
    actions = ["publish_articles", "unpublish_articles", "mark_as_sample"]

    @admin.display(description="Image")
    def image_preview(self, obj):
        if obj and obj.image_url:
            return format_html('<img src="{}" style="max-height:120px;border-radius:8px;" />', obj.image_url)
        return "No image"

    def save_model(self, request, obj, form, change):
        obj.body = sanitize_editorial_html(obj.body)
        if not obj.author_id and hasattr(request.user, "profile"):
            obj.author = request.user.profile
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "author" and not request.user.is_superuser:
            kwargs["queryset"] = Profile.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description="Publish selected articles")
    def publish_articles(self, request, queryset):
        queryset.update(status="published")
        self.message_user(request, f"{queryset.count()} article(s) published.")

    @admin.action(description="Move selected articles to drafts")
    def unpublish_articles(self, request, queryset):
        queryset.update(status="draft")
        self.message_user(request, f"{queryset.count()} article(s) moved to drafts.")

    @admin.action(description="Mark selected articles as sample content")
    def mark_as_sample(self, request, queryset):
        queryset.update(is_sample=True)
        self.message_user(request, f"{queryset.count()} article(s) marked as sample content.")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("name", "article", "body_preview", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("name", "email", "body", "article__title")
    actions = ["approve_comments", "reject_comments"]

    @admin.display(description="Comment")
    def body_preview(self, obj):
        return obj.body[:90]

    @admin.action(description="Approve selected comments")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} comment(s) approved.")

    @admin.action(description="Unapprove selected comments")
    def reject_comments(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} comment(s) hidden.")


@admin.register(BreakingNews)
class BreakingNewsAdmin(admin.ModelAdmin):
    list_display = ("headline", "article", "is_active", "priority", "expires_at", "created_at")
    list_editable = ("is_active", "priority")
    list_filter = ("is_active",)
    search_fields = ("headline",)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_active", "source", "created_at")
    list_filter = ("is_active", "source")
    search_fields = ("email", "name")
    actions = ["deactivate_subscribers"]

    @admin.action(description="Deactivate selected subscribers")
    def deactivate_subscribers(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} subscriber(s) deactivated.")


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published_at", "is_featured", "views")
    list_filter = ("category", "is_featured")
    search_fields = ("title", "description", "youtube_id")
    prepopulated_fields = {}


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ("name", "placement", "ad_type", "advertiser", "impressions", "clicks", "ctr", "is_active")
    list_filter = ("placement", "ad_type", "is_active")
    search_fields = ("name", "advertiser", "link_url")
    readonly_fields = ("impressions", "clicks", "created_at", "updated_at")
    fieldsets = (
        ("Campaign", {"fields": ("name", "advertiser", "placement", "ad_type", "is_active", "priority")}),
        ("Creative", {"fields": ("image", "image_url", "link_url", "html_snippet", "ad_slot")}),
        ("Schedule", {"fields": ("campaign_start", "campaign_end", "budget")}),
        ("Statistics", {"fields": ("impressions", "clicks", "created_at", "updated_at")}),
    )


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ("path", "article", "viewer_key", "created_at")
    list_filter = ("created_at",)
    search_fields = ("path", "article__title", "viewer_key")
    date_hierarchy = "created_at"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("subject", "name", "email", "message")
    actions = ["mark_read"]

    @admin.action(description="Mark selected messages as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} message(s) marked as read.")


@admin.register(NotificationSubscription)
class NotificationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active", "created_at")
    list_filter = ("is_active",)
