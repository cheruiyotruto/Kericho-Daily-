from django import forms
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.utils.text import slugify

from .models import (
    Advertisement,
    Article,
    BreakingNews,
    Category,
    Comment,
    ContactMessage,
    Locality,
    NewsletterSubscriber,
    Profile,
    Tag,
    Video,
)
from .utils import sanitize_editorial_html


class StyledMixin:
    def apply_widget_classes(self):
        for field in self.fields.values():
            current = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (current + " form-checkbox").strip()
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = (current + " form-select").strip()
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = (current + " form-textarea").strip()
            else:
                field.widget.attrs["class"] = (current + " form-input").strip()


class ArticleForm(StyledMixin, forms.ModelForm):
    published_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        label="Publish date / time",
    )
    locality_list = forms.ModelMultipleChoiceField(
        queryset=Locality.objects.all(), required=False, label="Kericho sub-counties / areas"
    )
    tag_list = forms.CharField(
        required=False,
        label="Tags (comma separated)",
        help_text="Example: tea farming, county government, community",
    )

    class Meta:
        model = Article
        fields = [
            "title", "subtitle", "excerpt", "body", "category", "featured_image",
            "featured_image_url", "image_caption", "image_credit", "status",
            "published_at", "is_featured", "is_breaking", "is_sponsored",
            "sponsor_name", "allow_comments", "is_sample", "seo_title",
            "seo_description", "canonical_url", "focus_keyword",
        ]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 18, "class": "editor-textarea"}),
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "seo_description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()
        self.fields["body"].widget.attrs["class"] = "editor-textarea"
        if self.instance and self.instance.pk:
            self.fields["locality_list"].initial = self.instance.localities.all()
            self.fields["tag_list"].initial = ", ".join(
                self.instance.tags.values_list("name", flat=True)
            )
            if self.instance.published_at:
                self.fields["published_at"].initial = self.instance.published_at.strftime(
                    "%Y-%m-%dT%H:%M"
                )

    def clean_body(self):
        body = sanitize_editorial_html(self.cleaned_data["body"])
        if len(body.strip()) < 80:
            raise forms.ValidationError("Please write at least a short article body (80+ characters).")
        return body

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 8:
            raise forms.ValidationError("Headlines should be at least 8 characters long.")
        return title

    def clean_tag_list(self):
        names = [
            name.strip() for name in self.cleaned_data.get("tag_list", "").split(",") if name.strip()
        ]
        return names[:12]

    save_m2m = None

    def save(self, commit=True, author=None):
        article = super().save(commit=False)
        if author is not None:
            article.author = author
        if not article.slug:
            base = slugify(article.title)[:150] or "article"
            slug = base
            counter = 2
            while Article.objects.filter(slug=slug).exclude(pk=article.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            article.slug = slug
        article.body = sanitize_editorial_html(article.body)
        if commit:
            article.save()
            self.save_m2m_manual(article)
        return article

    def save_m2m_manual(self, article):
        article.localities.set(self.cleaned_data.get("locality_list", []))
        tags = []
        for name in self.cleaned_data.get("tag_list", []):
            tag, _ = Tag.objects.get_or_create(
                slug=slugify(name), defaults={"name": name.title()}
            )
            tags.append(tag)
        article.tags.set(tags)


class CommentForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["name", "email", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5, "placeholder": "Share your view respectfully..."})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 10:
            raise forms.ValidationError("Your comment is too short.")
        return body


class NewsletterForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email", "name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()
        self.fields["email"].widget.attrs["placeholder"] = "you@example.com"
        self.fields["name"].widget.attrs["placeholder"] = "Your name (optional)"
        self.fields["name"].required = False

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ContactForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()


class BreakingNewsForm(StyledMixin, forms.ModelForm):
    published_headline = forms.CharField(required=False, label="Or use a published article headline")

    class Meta:
        model = BreakingNews
        fields = ["headline", "article", "is_active", "priority", "expires_at"]
        widgets = {"expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()
        self.fields["headline"].required = False
        self.fields["article"].queryset = Article.published.all()

    def clean(self):
        cleaned = super().clean()
        article = cleaned.get("article")
        headline = (cleaned.get("headline") or "").strip()
        if article and not headline:
            cleaned["headline"] = article.title
        if not article and not headline:
            raise forms.ValidationError("Add a headline or select a published article.")
        return cleaned


class AdvertisementForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Advertisement
        fields = [
            "name", "advertiser", "placement", "ad_type", "image", "image_url",
            "link_url", "html_snippet", "ad_slot", "campaign_start", "campaign_end",
            "budget", "priority", "is_active",
        ]
        widgets = {
            "campaign_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "campaign_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "html_snippet": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()


class ProfileForm(StyledMixin, forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = Profile
        fields = ["role", "bio", "phone", "is_journalist", "show_on_team_page", "facebook", "x_profile", "linkedin", "instagram"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()
        if self.instance and self.instance.user_id:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            user = profile.user
            user.first_name = self.cleaned_data.get("first_name", "")
            user.last_name = self.cleaned_data.get("last_name", "")
            user.save(update_fields=["first_name", "last_name"])
        return profile


class VideoForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Video
        fields = ["title", "description", "youtube_id", "thumbnail_url", "category", "duration", "published_at", "is_featured"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()
