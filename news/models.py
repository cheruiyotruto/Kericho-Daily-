from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .utils import reading_time_minutes, sanitize_editorial_html


ROLE_CHOICES = (
    ("super_admin", "Super Administrator"),
    ("managing_editor", "Managing Editor"),
    ("news_editor", "News Editor"),
    ("journalist", "Journalist / Reporter"),
    ("advertising_manager", "Advertising Manager"),
    ("moderator", "Moderator"),
    ("subscriber", "Subscriber"),
)

CATEGORY_CHOICES = (
    ("kericho-news", "Kericho News"),
    ("kenya-news", "Kenya News"),
    ("politics", "Politics"),
    ("business", "Business"),
    ("education", "Education"),
    ("crime-security", "Crime & Security"),
    ("entertainment", "Entertainment"),
    ("sports", "Sports"),
    ("technology", "Technology"),
    ("lifestyle", "Lifestyle"),
    ("opinion", "Opinion"),
)

PLACEMENT_CHOICES = (
    ("header", "Header banner"),
    ("homepage_sidebar", "Homepage sidebar"),
    ("between_cards", "Between article cards"),
    ("article_top", "Inside article — top"),
    ("article_inline", "Inside article — inline"),
    ("footer", "Footer advertisement"),
    ("mobile_banner", "Mobile advertising placement"),
)

AD_TYPE_CHOICES = (
    ("image", "Image banner"),
    ("html", "HTML / JavaScript snippet"),
    ("adsense", "Google AdSense"),
    ("ad_manager", "Google Ad Manager"),
)

STATUS_CHOICES = (
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("published", "Published"),
    ("archived", "Archived"),
)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#123B32")
    show_in_nav = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:category", kwargs={"slug": self.slug})

    @property
    def article_count(self):
        return self.articles.filter(status="published", published_at__lte=timezone.now()).count()


class Locality(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:locality", kwargs={"slug": self.slug})


class Profile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="subscriber")
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="authors/", blank=True, null=True)
    phone = models.CharField(max_length=40, blank=True)
    facebook = models.URLField(blank=True)
    x_profile = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    is_journalist = models.BooleanField(default=False)
    show_on_team_page = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        full = f"{self.user.first_name} {self.user.last_name}".strip()
        return full or self.user.get_username()

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.display_name) or self.user.username
            slug = base
            counter = 2
            while Profile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news:author", kwargs={"slug": self.slug})

    @property
    def published_articles(self):
        return self.articles.filter(status="published", published_at__lte=timezone.now())


class Tag(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PublishedArticleManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status="published", published_at__lte=timezone.now())
            .select_related("category", "author__user")
        )


class Article(TimeStampedModel):
    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=220, unique=True)
    subtitle = models.CharField(max_length=360, blank=True)
    excerpt = models.TextField(max_length=600, blank=True)
    body = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="articles")
    localities = models.ManyToManyField(Locality, blank=True, related_name="articles")
    author = models.ForeignKey(Profile, on_delete=models.PROTECT, related_name="articles")
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")
    featured_image = models.ImageField(upload_to="articles/%Y/%m/", blank=True, null=True)
    featured_image_url = models.URLField(
        blank=True,
        help_text="Optional external image URL used when no image is uploaded.",
    )
    image_caption = models.CharField(max_length=300, blank=True)
    image_credit = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_featured = models.BooleanField(default=False)
    is_breaking = models.BooleanField(default=False)
    is_sponsored = models.BooleanField(default=False)
    sponsor_name = models.CharField(max_length=140, blank=True)
    allow_comments = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    reading_time = models.PositiveIntegerField(default=1, editable=False)
    is_sample = models.BooleanField(default=True)

    # Attribution for headlines imported from external news sources
    source_url = models.URLField(blank=True)
    source_name = models.CharField(max_length=120, blank=True)

    # SEO metadata
    seo_title = models.CharField(max_length=160, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    canonical_url = models.URLField(blank=True)
    focus_keyword = models.CharField(max_length=120, blank=True)

    objects = models.Manager()
    published = PublishedArticleManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "published_at"]),
            models.Index(fields=["category", "status", "published_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = sanitize_editorial_html(self.body)
        self.reading_time = reading_time_minutes(self.body)
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            "news:article",
            kwargs={"category_slug": self.category.slug, "slug": self.slug},
        )

    @property
    def image_url(self):
        if self.featured_image:
            return self.featured_image.url
        if self.featured_image_url:
            return self.featured_image_url
        return "/static/images/placeholder-news.svg"

    @property
    def display_title(self):
        return f"SAMPLE: {self.title}" if self.is_sample and not self.title.lower().startswith("sample") else self.title

    @property
    def meta_title(self):
        return self.seo_title or f"{self.title} | {settings.SITE_NAME}"

    @property
    def meta_description(self):
        return self.seo_description or self.excerpt or self.subtitle or settings.SITE_TAGLINE

    def increment_view(self, request=None):
        Article.objects.filter(pk=self.pk).update(views_count=F("views_count") + 1)
        self.views_count += 1
        viewer_key = ""
        if request:
            viewer_key = request.session.session_key or ""
            PageView.objects.create(
                article=self,
                path=request.path,
                viewer_key=viewer_key,
                referrer=request.META.get("HTTP_REFERER", "")[:500],
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            )

    def related_articles(self, limit=4):
        qs = Article.published.exclude(pk=self.pk)
        return (
            qs.filter(
                Q(category=self.category)
                | Q(tags__in=self.tags.all())
                | Q(localities__in=self.localities.all())
            )
            .distinct()
            .order_by("-published_at")[:limit]
        )


class Comment(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    body = models.TextField(max_length=2000)
    is_approved = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} on {self.article.title}"

    def get_initial(self):
        return (self.name or "R")[:1].upper()


class BreakingNews(TimeStampedModel):
    headline = models.CharField(max_length=300)
    article = models.ForeignKey(
        Article, on_delete=models.SET_NULL, null=True, blank=True, related_name="breaking_entries"
    )
    link = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority", "-created_at"]

    def __str__(self):
        return self.headline

    @property
    def target_url(self):
        if self.article:
            return self.article.get_absolute_url()
        return self.link or "#"

    @property
    def currently_active(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class NewsletterSubscriber(TimeStampedModel):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120, blank=True)
    token = models.CharField(max_length=64, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=80, default="website")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets

            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Video(TimeStampedModel):
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    youtube_id = models.CharField(
        max_length=30, help_text="YouTube video ID, e.g. dQw4w9WgXcQ"
    )
    thumbnail_url = models.URLField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    duration = models.CharField(max_length=20, blank=True)
    views = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(default=timezone.now)
    is_featured = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title

    @property
    def thumbnail(self):
        if self.thumbnail_url:
            return self.thumbnail_url
        return f"https://i.ytimg.com/vi/{self.youtube_id}/hqdefault.jpg"

    @property
    def embed_url(self):
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_id}"


class Advertisement(TimeStampedModel):
    name = models.CharField(max_length=160)
    advertiser = models.CharField(max_length=160, blank=True)
    placement = models.CharField(max_length=30, choices=PLACEMENT_CHOICES, db_index=True)
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES, default="image")
    image = models.ImageField(upload_to="advertisements/%Y/%m/", blank=True, null=True)
    image_url = models.URLField(blank=True)
    link_url = models.URLField(blank=True)
    html_snippet = models.TextField(blank=True)
    ad_slot = models.CharField(max_length=80, blank=True, help_text="AdSense/Ad Manager slot ID")
    campaign_start = models.DateTimeField(null=True, blank=True)
    campaign_end = models.DateTimeField(null=True, blank=True)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-priority", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_placement_display()})"

    @property
    def image_src(self):
        if self.image:
            return self.image.url
        return self.image_url

    @property
    def click_url(self):
        return reverse("ad_click", args=[self.pk])

    def is_currently_active(self, now=None):
        now = now or timezone.now()
        if not self.is_active:
            return False
        if self.campaign_start and self.campaign_start > now:
            return False
        if self.campaign_end and self.campaign_end < now:
            return False
        return True

    def register_impression(self):
        Advertisement.objects.filter(pk=self.pk).update(impressions=F("impressions") + 1)

    def register_click(self):
        Advertisement.objects.filter(pk=self.pk).update(clicks=F("clicks") + 1)

    @property
    def ctr(self):
        if not self.impressions:
            return 0
        return round((self.clicks / self.impressions) * 100, 2)


class PageView(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, null=True, blank=True, related_name="page_views")
    path = models.CharField(max_length=400)
    viewer_key = models.CharField(max_length=120, blank=True, db_index=True)
    referrer = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.name}"


class NotificationSubscription(TimeStampedModel):
    endpoint = models.TextField(unique=True)
    auth = models.CharField(max_length=200, blank=True)
    p256dh = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Notification subscription ({'active' if self.is_active else 'inactive'})"
