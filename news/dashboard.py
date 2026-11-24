import csv
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AdvertisementForm, ArticleForm, BreakingNewsForm, ProfileForm, VideoForm
from .models import (
    Advertisement,
    Article,
    BreakingNews,
    Category,
    Comment,
    ContactMessage,
    NewsletterSubscriber,
    PageView,
    Profile,
    Video,
)
from .permissions import (
    current_role,
    is_ad_manager,
    is_editorial,
    is_moderator,
    is_senior_editor,
    is_staff_user,
    staff_required,
)


def _paginate(queryset, request, per_page=15):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def _scoped_articles(request):
    role = current_role(request.user)
    qs = Article.objects.select_related("category", "author__user")
    if role == "journalist" and not request.user.is_superuser:
        qs = qs.filter(author__user=request.user)
    return qs


def _daily_page_views(days=7):
    since = timezone.now() - timedelta(days=days)
    rows = (
        PageView.objects.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    data = {row["day"]: row["count"] for row in rows}
    result = []
    for offset in range(days - 1, -1, -1):
        day = (timezone.now() - timedelta(days=offset)).date()
        result.append({"day": day.strftime("%a"), "count": data.get(day, 0)})
    return result


@staff_required
def home(request):
    role = current_role(request.user)
    articles = _scoped_articles(request)
    weekly_views = _daily_page_views(7)
    context = {
        "page_title": "Newsroom Dashboard | KERICHO DAILY",
        "role_label": request.user.profile.get_role_display() if hasattr(request.user, "profile") else role,
        "total_articles": articles.count(),
        "published_articles": articles.filter(status="published").count(),
        "draft_articles": articles.filter(status="draft").count(),
        "scheduled_articles": articles.filter(status="scheduled").count(),
        "total_views": articles.aggregate(total=Sum("views_count"))["total"] or 0,
        "pending_comments": Comment.objects.filter(is_approved=False).count(),
        "subscriber_count": NewsletterSubscriber.objects.filter(is_active=True).count(),
        "active_ads": Advertisement.objects.filter(is_active=True).count(),
        "ad_impressions": Advertisement.objects.aggregate(total=Sum("impressions"))["total"] or 0,
        "ad_clicks": Advertisement.objects.aggregate(total=Sum("clicks"))["total"] or 0,
        "recent_articles": articles.order_by("-updated_at")[:6],
        "recent_comments": Comment.objects.filter(is_approved=False).select_related("article")[:5],
        "top_articles": Article.published.order_by("-views_count")[:5],
        "unread_messages": ContactMessage.objects.filter(is_read=False).count(),
        "page_views": weekly_views,
        "chart_max": max([p["count"] for p in weekly_views] + [1]),
        "can_edit_articles": is_editorial(request.user),
        "can_moderate": is_moderator(request.user),
        "can_manage_ads": is_ad_manager(request.user),
        "can_manage_team": is_senior_editor(request.user),
    }
    return render(request, "dashboard/home.html", context)


@staff_required(role_check=is_editorial)
def article_list(request):
    qs = _scoped_articles(request)
    status = request.GET.get("status", "")
    category_slug = request.GET.get("category", "")
    query = request.GET.get("q", "")
    if status:
        qs = qs.filter(status=status)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(slug__icontains=query) | Q(body__icontains=query))
    context = {
        "page_title": "Articles | KERICHO DAILY Dashboard",
        "articles": _paginate(qs.order_by("-updated_at"), request),
        "status": status,
        "category_slug": category_slug,
        "query": query,
        "categories": Category.objects.all(),
        "can_publish": is_senior_editor(request.user),
    }
    return render(request, "dashboard/article_list.html", context)


@staff_required(role_check=is_editorial)
def article_edit(request, article_id=None):
    article = get_object_or_404(_scoped_articles(request), pk=article_id) if article_id else None
    if article and not is_senior_editor(request.user) and article.author.user_id != request.user.pk:
        messages.error(request, "You can only edit your own articles.")
        return redirect("dashboard:article_list")

    if request.method == "POST":
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if is_senior_editor(request.user):
            form.fields["author"] = UserModelChoiceField()
        if form.is_valid():
            author = article.author if article else request.user.profile
            if is_senior_editor(request.user) and form.cleaned_data.get("author"):
                author = form.cleaned_data["author"]
            status_value = form.cleaned_data.get("status")
            if not is_senior_editor(request.user):
                if not article or article.status != "published":
                    status_value = "draft"
                    if request.POST.get("status") in {"scheduled", "published"}:
                        messages.info(request, "Reporters save drafts; an editor will publish your story.")
                else:
                    status_value = "published"
            obj = form.save(commit=False, author=author)
            obj.status = status_value
            obj.save()
            form.save_m2m_manual(obj)
            action = "updated" if article else "created"
            messages.success(request, f"Article {action} successfully.")
            return redirect("dashboard:article_list")
    else:
        form = ArticleForm(instance=article)
        if is_senior_editor(request.user):
            form.fields["author"] = UserModelChoiceField(initial=article.author if article else None)

    return render(
        request,
        "dashboard/article_edit.html",
        {
            "page_title": ("Edit Article" if article else "New Article") + " | KERICHO DAILY Dashboard",
            "form": form,
            "article": article,
            "can_publish": is_senior_editor(request.user),
        },
    )


class UserModelChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("queryset", Profile.objects.filter(user__is_active=True).select_related("user"))
        kwargs.setdefault("label", "Author / by-line")
        kwargs.setdefault("required", False)
        kwargs.setdefault("widget", forms.Select(attrs={"class": "form-select"}))
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return f"{obj.display_name} ({obj.get_role_display()})"


@require_POST
@staff_required(role_check=is_editorial)
def article_delete(request, article_id):
    article = get_object_or_404(Article, pk=article_id)
    allowed = is_senior_editor(request.user) or (
        article.author.user_id == request.user.pk and article.status in {"draft", "scheduled"}
    )
    if not allowed:
        messages.error(request, "You cannot delete this article.")
        return redirect("dashboard:article_list")
    title = article.title
    article.delete()
    messages.success(request, f"Deleted: {title}")
    return redirect("dashboard:article_list")


@staff_required(role_check=is_moderator)
def comments(request):
    qs = Comment.objects.select_related("article", "user")
    status = request.GET.get("status", "pending")
    if status == "pending":
        qs = qs.filter(is_approved=False)
    elif status == "approved":
        qs = qs.filter(is_approved=True)
    return render(
        request,
        "dashboard/comments.html",
        {
            "page_title": "Comments | KERICHO DAILY Dashboard",
            "comments": _paginate(qs.order_by("-created_at"), request, 20),
            "status": status,
        },
    )


@require_POST
@staff_required(role_check=is_moderator)
def comment_moderate(request, comment_id, action):
    comment = get_object_or_404(Comment, pk=comment_id)
    comment.is_approved = action == "approve"
    comment.save(update_fields=["is_approved", "updated_at"])
    messages.success(request, "Comment approved." if comment.is_approved else "Comment hidden.")
    return redirect(request.META.get("HTTP_REFERER", "dashboard:comments"))


@staff_required(role_check=is_senior_editor)
def breaking(request):
    return render(
        request,
        "dashboard/breaking.html",
        {
            "page_title": "Breaking News | KERICHO DAILY Dashboard",
            "items": BreakingNews.objects.select_related("article")[:30],
            "form": BreakingNewsForm(),
        },
    )


@require_POST
@staff_required(role_check=is_senior_editor)
def breaking_create(request):
    form = BreakingNewsForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        if not item.headline and item.article:
            item.headline = item.article.title
        item.save()
        messages.success(request, "Breaking news item added.")
    else:
        messages.error(request, "Please check the breaking news form.")
    return redirect("dashboard:breaking")


@require_POST
@staff_required(role_check=is_senior_editor)
def breaking_toggle(request, item_id):
    item = get_object_or_404(BreakingNews, pk=item_id)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active", "updated_at"])
    from django.core.cache import cache

    cache.delete("active_breaking")
    messages.success(request, "Breaking news status updated.")
    return redirect("dashboard:breaking")


@require_POST
@staff_required(role_check=is_senior_editor)
def breaking_delete(request, item_id):
    get_object_or_404(BreakingNews, pk=item_id).delete()
    from django.core.cache import cache

    cache.delete("active_breaking")
    messages.success(request, "Breaking news item removed.")
    return redirect("dashboard:breaking")


@staff_required(role_check=is_ad_manager)
def advertisements(request):
    ads = Advertisement.objects.all()
    return render(
        request,
        "dashboard/advertisements.html",
        {
            "page_title": "Advertisements | KERICHO DAILY Dashboard",
            "ads": ads,
            "total_impressions": ads.aggregate(total=Sum("impressions"))["total"] or 0,
            "total_clicks": ads.aggregate(total=Sum("clicks"))["total"] or 0,
            "revenue": ads.aggregate(total=Sum("budget"))["total"] or 0,
        },
    )


@staff_required(role_check=is_ad_manager)
def advertisement_edit(request, ad_id=None):
    ad = get_object_or_404(Advertisement, pk=ad_id) if ad_id else None
    if request.method == "POST":
        form = AdvertisementForm(request.POST, request.FILES, instance=ad)
        if form.is_valid():
            form.save()
            messages.success(request, "Campaign saved.")
            return redirect("dashboard:advertisements")
    else:
        form = AdvertisementForm(instance=ad)
    return render(
        request,
        "dashboard/form.html",
        {
            "page_title": ("Edit Campaign" if ad else "New Campaign") + " | KERICHO DAILY",
            "form": form,
            "heading": "Edit advertising campaign" if ad else "Create advertising campaign",
            "back_url": "dashboard:advertisements",
        },
    )


@staff_required
def subscribers(request):
    qs = NewsletterSubscriber.objects.all()
    status = request.GET.get("status", "active")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    return render(
        request,
        "dashboard/subscribers.html",
        {
            "page_title": "Newsletter Subscribers | KERICHO DAILY Dashboard",
            "subscribers": _paginate(qs.order_by("-created_at"), request, 25),
            "status": status,
        },
    )


@staff_required
def subscribers_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="kericho-daily-subscribers.csv"'
    writer = csv.writer(response)
    writer.writerow(["email", "name", "is_active", "source", "created_at"])
    for subscriber in NewsletterSubscriber.objects.all().order_by("-created_at"):
        writer.writerow(
            [subscriber.email, subscriber.name, subscriber.is_active, subscriber.source, subscriber.created_at.isoformat()]
        )
    return response


@staff_required(role_check=is_senior_editor)
def journalists(request):
    profiles = Profile.objects.select_related("user").order_by("user__first_name")
    return render(
        request,
        "dashboard/journalists.html",
        {
            "page_title": "Journalists | KERICHO DAILY Dashboard",
            "profiles": profiles,
        },
    )


@staff_required(role_check=is_senior_editor)
def journalist_edit(request, profile_id):
    profile = get_object_or_404(Profile, pk=profile_id)
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {profile.display_name}.")
            return redirect("dashboard:journalists")
    else:
        form = ProfileForm(instance=profile)
    return render(
        request,
        "dashboard/form.html",
        {
            "page_title": "Edit Journalist | KERICHO DAILY",
            "form": form,
            "heading": f"Edit {profile.display_name}",
            "back_url": "dashboard:journalists",
        },
    )


@staff_required(role_check=is_editorial)
def videos(request):
    videos_qs = Video.objects.all()
    return render(
        request,
        "dashboard/videos.html",
        {
            "page_title": "Videos | KERICHO DAILY Dashboard",
            "videos": videos_qs,
        },
    )


@staff_required(role_check=is_editorial)
def video_edit(request, video_id=None):
    video = get_object_or_404(Video, pk=video_id) if video_id else None
    if request.method == "POST":
        form = VideoForm(request.POST, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, "Video saved.")
            return redirect("dashboard:videos")
    else:
        form = VideoForm(instance=video)
    return render(
        request,
        "dashboard/form.html",
        {
            "page_title": ("Edit Video" if video else "New Video") + " | KERICHO DAILY",
            "form": form,
            "heading": "Video item",
            "back_url": "dashboard:videos",
        },
    )


@staff_required
def analytics(request):
    days = int(request.GET.get("days", 30))
    if days not in {7, 14, 30, 90}:
        days = 30
    since = timezone.now() - timedelta(days=days)
    top_articles = (
        Article.objects.annotate(views=Count("page_views", filter=Q(page_views__created_at__gte=since)))
        .order_by("-views", "-views_count")[:10]
    )
    referrers = (
        PageView.objects.filter(created_at__gte=since)
        .exclude(referrer="")
        .values("referrer")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    chart = _daily_page_views(min(days, 14))
    context = {
        "page_title": "Analytics | KERICHO DAILY Dashboard",
        "days": days,
        "chart_max": max([p["count"] for p in chart] + [1]),
        "total_page_views": PageView.objects.filter(created_at__gte=since).count(),
        "unique_visitors": PageView.objects.filter(created_at__gte=since)
        .values("viewer_key")
        .distinct()
        .count(),
        "chart": chart,
        "top_articles": top_articles,
        "referrers": referrers,
        "device_breakdown": [
            {"label": "Mobile", "count": PageView.objects.filter(created_at__gte=since, user_agent__icontains="mobile").count()},
            {"label": "Desktop / other", "count": PageView.objects.filter(created_at__gte=since).exclude(user_agent__icontains="mobile").count()},
        ],
    }
    return render(request, "dashboard/analytics.html", context)


@staff_required
def contact_messages(request):
    if request.method == "POST":
        message_id = request.POST.get("message_id")
        if message_id:
            ContactMessage.objects.filter(pk=message_id).update(is_read=True)
            messages.success(request, "Message marked as read.")
    return render(
        request,
        "dashboard/messages.html",
        {
            "page_title": "Messages | KERICHO DAILY Dashboard",
            "messages": ContactMessage.objects.all()[:50],
        },
    )
