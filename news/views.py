from datetime import timedelta
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommentForm, ContactForm, NewsletterForm
from .models import (
    Advertisement,
    Article,
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
from .utils import plain_text, sanitize_editorial_html


def health(request):
    """Lightweight readiness endpoint for deployment and local monitoring."""
    return JsonResponse({"status": "ok", "service": "kericho-daily"})


# ---------------------------------------------------------------------------
# Branded error pages. These templates are intentionally self-contained so a
# 500 caused by a database outage cannot fail again while rendering the page.
# ---------------------------------------------------------------------------
def _error_page(request, template, status, title):
    return render(
        request,
        template,
        {"page_title": f"{status} {title} | {settings.SITE_NAME}"},
        status=status,
    )


def error_400(request, exception=None):
    return _error_page(request, "400.html", 400, "Bad Request")


def error_403(request, exception=None):
    return _error_page(request, "403.html", 403, "Forbidden")


def error_404(request, exception=None):
    return _error_page(request, "404.html", 404, "Page Not Found")


def error_500(request):
    return _error_page(request, "500.html", 500, "Server Error")


def paginate(queryset, page_number, per_page=9):
    paginator = Paginator(queryset, per_page)
    try:
        return paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        return paginator.get_page(1)


def _pick_unique(qs, exclude_ids, limit):
    picked = []
    for item in qs:
        if item.pk not in exclude_ids:
            picked.append(item)
            exclude_ids.add(item.pk)
        if len(picked) >= limit:
            break
    return picked


def home(request):
    """Editor-designed homepage: hero, supporting stories, latest, county and video."""
    now = timezone.now()
    all_published = Article.published.all()
    featured_qs = all_published.filter(is_featured=True).order_by("-published_at")
    latest_qs = all_published.order_by("-published_at")

    hero = featured_qs.first() or latest_qs.first()
    used = {hero.pk} if hero else set()
    supporting = _pick_unique(featured_qs.exclude(pk=hero.pk) if hero else [], used, 3)
    if len(supporting) < 3:
        supporting += _pick_unique(latest_qs, used, 3 - len(supporting))

    latest_page = paginate(all_published.exclude(pk__in=used), request.GET.get("page"), 9)

    if request.GET.get("partial"):
        return render(request, "includes/latest_partial.html", {"latest": latest_page})

    county_qs = all_published.filter(category__slug="kericho-news")
    county = list(county_qs[:6])
    if len(county) < 6:
        county += list(
            all_published.filter(localities__isnull=False)
            .exclude(pk__in=[a.pk for a in county])
            .distinct()[: 6 - len(county)]
        )

    trending = list(all_published.order_by("-views_count", "-published_at")[:6])
    entertainment = list(
        all_published.filter(category__slug__in=["entertainment", "sports"]).order_by("-published_at")[:4]
    )
    if not entertainment:
        entertainment = _pick_unique(latest_qs, used | {a.pk for a in county}, 4)

    featured_video = Video.objects.filter(is_featured=True).order_by("-published_at").first()
    more_videos = Video.objects.exclude(pk=featured_video.pk if featured_video else -1).order_by("-published_at")[:3]

    county_name = "Kericho County"
    context = {
        "page_title": f"{settings.SITE_NAME} — {settings.SITE_TAGLINE}",
        "page_description": "Breaking news, Kericho County updates, Kenyan politics, business, sports and community stories from Kericho Daily.",
        "hero": hero,
        "supporting": supporting,
        "latest": latest_page,
        "county_articles": county,
        "trending": trending,
        "entertainment_articles": entertainment,
        "featured_video": featured_video,
        "more_videos": more_videos,
        "county_name": county_name,
        "canonical_url": request.build_absolute_uri("/"),
        "og_type": "website",
    }
    return render(request, "home.html", context)


def category(request, slug):
    category_obj = get_object_or_404(Category, slug=slug)
    qs = Article.published.filter(category=category_obj)
    locality_slug = request.GET.get("locality")
    selected_locality = None
    if locality_slug:
        selected_locality = get_object_or_404(Locality, slug=locality_slug)
        qs = qs.filter(localities=selected_locality)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(body__icontains=query))

    articles = paginate(qs, request.GET.get("page"), 9)
    trending = Article.published.order_by("-views_count")[:5]
    context = {
        "page_title": f"{category_obj.name} News | {settings.SITE_NAME}",
        "page_description": category_obj.meta_description or category_obj.description or f"Latest {category_obj.name} stories on {settings.SITE_NAME}.",
        "archive_title": category_obj.name,
        "archive_description": category_obj.description or f"Latest {category_obj.name} stories on {settings.SITE_NAME}.",
        "category_obj": category_obj,
        "selected_locality": selected_locality,
        "articles": articles,
        "trending": trending,
        "query": query,
        "canonical_url": request.build_absolute_uri(request.path),
        "og_type": "website",
    }
    return render(request, "category.html", context)


def locality(request, slug):
    locality_obj = get_object_or_404(Locality, slug=slug)
    articles = paginate(
        Article.published.filter(localities=locality_obj), request.GET.get("page"), 9
    )
    context = {
        "page_title": f"{locality_obj.name} News | {settings.SITE_NAME}",
        "page_description": locality_obj.description or f"Local news and community stories from {locality_obj.name}.",
        "archive_title": locality_obj.name,
        "archive_description": locality_obj.description or f"Local news and community stories from {locality_obj.name}.",
        "category_obj": None,
        "locality_obj": locality_obj,
        "articles": articles,
        "trending": Article.published.order_by("-views_count")[:5],
        "canonical_url": request.build_absolute_uri(request.path),
        "og_type": "website",
    }
    return render(request, "category.html", context)


def tag_articles(request, slug):
    tag_obj = get_object_or_404(Tag, slug=slug)
    articles = paginate(
        Article.published.filter(tags=tag_obj), request.GET.get("page"), 9
    )
    return render(
        request,
        "category.html",
        {
            "page_title": f"{tag_obj.name} — {settings.SITE_NAME}",
            "page_description": f"Stories tagged {tag_obj.name}.",
            "archive_title": tag_obj.name,
            "archive_description": f"Stories tagged {tag_obj.name}.",
            "tag_obj": tag_obj,
            "category_obj": None,
            "articles": articles,
            "trending": Article.published.order_by("-views_count")[:5],
            "canonical_url": request.build_absolute_uri(request.path),
            "og_type": "website",
        },
    )


def author_profile(request, slug):
    profile = get_object_or_404(
        Profile.objects.select_related("user").prefetch_related("articles"), slug=slug
    )
    articles = paginate(profile.published_articles, request.GET.get("page"), 9)
    return render(
        request,
        "author.html",
        {
            "page_title": f"{profile.display_name} | {settings.SITE_NAME}",
            "page_description": profile.bio or f"Read stories by {profile.display_name}.",
            "profile": profile,
            "articles": articles,
            "canonical_url": request.build_absolute_uri(request.path),
            "og_type": "profile",
        },
    )


def search(request):
    query = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "")
    qs = Article.published.all()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(subtitle__icontains=query)
            | Q(excerpt__icontains=query)
            | Q(body__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(author__user__first_name__icontains=query)
        ).distinct()
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    articles = paginate(qs.order_by("-published_at"), request.GET.get("page"), 10)
    return render(
        request,
        "search.html",
        {
            "page_title": f"Search: {query or 'Articles'} | {settings.SITE_NAME}",
            "page_description": "Search stories from Kericho Daily.",
            "query": query,
            "category_slug": category_slug,
            "articles": articles,
            "categories": Category.objects.all(),
            "result_count": qs.count(),
            "canonical_url": request.build_absolute_uri(request.path),
            "og_type": "website",
        },
    )


def article_detail(request, category_slug, slug):
    article = get_object_or_404(
        Article.published.select_related("category", "author__user", "author")
        .prefetch_related("tags", "localities"),
        category__slug=category_slug,
        slug=slug,
    )
    article.increment_view(request)

    comments = article.comments.filter(is_approved=True).order_by("created_at")
    trending = Article.published.exclude(pk=article.pk).order_by("-views_count")[:5]
    related = list(article.related_articles(4))
    if len(related) < 4:
        related += list(
            Article.published.exclude(pk=article.pk).exclude(pk__in=[a.pk for a in related])[
                : 4 - len(related)
            ]
        )

    absolute_url = request.build_absolute_uri(article.get_absolute_url())
    image_url = request.build_absolute_uri(article.image_url) if article.image_url.startswith("/") else article.image_url
    share_text = quote(f"{article.title} — {settings.SITE_NAME}")
    share_url = quote(absolute_url)
    schema = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": article.title,
        "description": article.meta_description,
        "image": [image_url],
        "datePublished": article.published_at.isoformat(),
        "dateModified": article.updated_at.isoformat(),
        "author": {
            "@type": "Person",
            "name": article.author.display_name,
            "url": request.build_absolute_uri(article.author.get_absolute_url()),
        },
        "publisher": {
            "@type": "Organization",
            "name": settings.SITE_NAME,
            "logo": {
                "@type": "ImageObject",
                "url": request.build_absolute_uri("/static/images/logo-schema.png"),
                "width": 600,
                "height": 120,
            },
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": absolute_url},
        "articleSection": article.category.name,
        "keywords": ", ".join(article.tags.values_list("name", flat=True)),
    }
    context = {
        "page_title": article.meta_title,
        "page_description": article.meta_description,
        "article": article,
        "comments": comments,
        "comment_form": CommentForm(),
        "related": related,
        "trending": trending,
        "share_links": {
            "facebook": f"https://www.facebook.com/sharer/sharer.php?u={share_url}",
            "x": f"https://twitter.com/intent/tweet?text={share_text}&url={share_url}",
            "whatsapp": f"https://api.whatsapp.com/send?text={share_text}%20{share_url}",
            "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={share_url}",
            "email": f"mailto:?subject={share_text}&body={share_url}",
        },
        "schema": schema,
        "canonical_url": article.canonical_url or absolute_url,
        "og_type": "article",
        "og_image": image_url,
        "published_time": article.published_at.isoformat(),
    }
    return render(request, "article.html", context)


@require_POST
def comment_create(request, article_id):
    article = get_object_or_404(Article.published, pk=article_id)
    if not article.allow_comments:
        messages.error(request, "Comments are closed for this story.")
        return redirect(article.get_absolute_url())

    # Simple spam protection: hidden field plus per-session rate limit.
    if request.POST.get("website"):
        messages.success(request, "Thank you. Your comment has been received for review.")
        return redirect(article.get_absolute_url())

    rate_key = f"comment-{request.session.session_key or 'anon'}"
    if cache.get(rate_key):
        messages.warning(request, "Please wait a moment before posting another comment.")
        return redirect(article.get_absolute_url())

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        if request.user.is_authenticated:
            comment.user = request.user
            comment.name = comment.name or request.user.get_full_name() or request.user.get_username()
            comment.email = comment.email or request.user.email
        comment.article = article
        comment.body = plain_text(comment.body)
        comment.ip_address = request.META.get("REMOTE_ADDR") or None
        comment.is_approved = request.user.is_staff and request.user.is_superuser
        comment.save()
        cache.set(rate_key, True, 60)
        messages.success(
            request,
            "Thank you. Your comment is awaiting editorial moderation before it appears publicly.",
        )
    else:
        messages.error(request, "Please check the comment form and try again.")
    return redirect(article.get_absolute_url() + "#comments")


def videos(request):
    videos_qs = Video.objects.select_related("category").order_by("-published_at")
    featured = videos_qs.filter(is_featured=True).first()
    remaining = videos_qs.exclude(pk=featured.pk if featured else -1)
    return render(
        request,
        "videos.html",
        {
            "page_title": f"Video News | {settings.SITE_NAME}",
            "page_description": "Kericho Daily video reports, interviews and community features.",
            "featured": featured,
            "videos": paginate(remaining, request.GET.get("page"), 9),
            "canonical_url": request.build_absolute_uri(request.path),
            "og_type": "website",
        },
    )


def video_detail(request, video_id):
    video = get_object_or_404(Video, pk=video_id)
    Video.objects.filter(pk=video.pk).update(views=F("views") + 1)
    return render(
        request,
        "video_detail.html",
        {
            "page_title": f"{video.title} | {settings.SITE_NAME}",
            "page_description": video.description[:300],
            "video": video,
            "more_videos": Video.objects.exclude(pk=video.pk).order_by("-published_at")[:4],
            "canonical_url": request.build_absolute_uri(request.path),
            "og_type": "video.other",
            "og_image": video.thumbnail,
        },
    )


@require_POST
def newsletter_subscribe(request):
    form = NewsletterForm(request.POST)
    wants_json = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
    )
    if form.is_valid():
        email = form.cleaned_data["email"].lower()
        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            defaults={
                "name": form.cleaned_data.get("name", ""),
                "source": request.POST.get("source", "website"),
            },
        )
        if not created:
            subscriber.is_active = True
            subscriber.save(update_fields=["is_active", "updated_at"])
        if wants_json:
            return JsonResponse({"ok": True, "message": "You're subscribed. Welcome to Kericho Daily!"})
        messages.success(request, "You're subscribed. Welcome to Kericho Daily!")
    else:
        error = "Please enter a valid email address."
        if wants_json:
            return JsonResponse({"ok": False, "message": error}, status=400)
        messages.error(request, error)
    return redirect(request.META.get("HTTP_REFERER", "/") + "#newsletter")


def newsletter_unsubscribe(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, token=token)
    subscriber.is_active = False
    subscriber.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "You have been unsubscribed from the Kericho Daily newsletter.")
    return redirect("news:home")


@require_POST
def notification_subscribe(request):
    try:
        payload = request.json() if hasattr(request, "json") else {}
    except Exception:
        payload = {}
    if not payload:
        import json

        try:
            payload = json.loads(request.body or b"{}")
        except (ValueError, TypeError):
            payload = {}
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint.startswith(("http://", "https://")):
        return JsonResponse({"ok": False, "message": "Invalid subscription endpoint."}, status=400)
    keys = payload.get("keys") or {}
    NotificationSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "auth": keys.get("auth", ""),
            "p256dh": keys.get("p256dh", ""),
            "user": request.user if request.user.is_authenticated else None,
            "is_active": True,
        },
    )
    return JsonResponse({"ok": True, "message": "Breaking news alerts enabled."})


def ad_impression(request, ad_id):
    ad = get_object_or_404(Advertisement, pk=ad_id, is_active=True)
    session_key = request.session.session_key or request.META.get("REMOTE_ADDR", "anon")
    throttle_key = f"ad-impr-{ad_id}-{session_key}"
    if not cache.get(throttle_key):
        ad.register_impression()
        cache.set(throttle_key, True, 300)
    transparent_gif = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
        b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00"
        b"\x01\x00\x00\x02\x02D\x01\x00;"
    )
    return HttpResponse(transparent_gif, content_type="image/gif")


def ad_click(request, ad_id):
    ad = get_object_or_404(Advertisement, pk=ad_id, is_active=True)
    ad.register_click()
    return redirect(ad.link_url or "/")


def service_worker(request):
    """Serve the service worker from the root so its scope covers the whole site."""
    from django.conf import settings

    path = settings.BASE_DIR / "static" / "sw.js"
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="application/javascript")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /accounts/",
        "Disallow: /search",
        "Disallow: /comment/",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
        f"News sitemap: {settings.SITE_URL}/news-sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def _urlset(urls):
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, priority in urls:
        priority_value = float(priority)
        parts.append(
            "<url><loc>{}</loc><lastmod>{}</lastmod><changefreq>{}</changefreq><priority>{}</priority></url>".format(
                xml_escape(loc),
                lastmod,
                "daily" if priority_value >= 0.8 else "weekly",
                priority_value,
            )
        )
    parts.append("</urlset>")
    return "".join(parts)


def sitemap_xml(request):
    today = timezone.now().strftime("%Y-%m-%d")
    urls = [(settings.SITE_URL + "/", today, "1.0")]
    for path in ["/about/", "/contact/", "/advertise/", "/videos/", "/corrections/", "/privacy/", "/terms/"]:
        urls.append((settings.SITE_URL + path, today, "0.5"))
    for category_obj in Category.objects.all():
        urls.append((settings.SITE_URL + category_obj.get_absolute_url(), today, "0.7"))
    for article in Article.published.select_related("category")[:2000]:
        urls.append(
            (
                settings.SITE_URL + article.get_absolute_url(),
                article.updated_at.strftime("%Y-%m-%d"),
                "0.9" if article.is_featured else "0.7",
            )
        )
    return HttpResponse(_urlset(urls), content_type="application/xml")


def news_sitemap_xml(request):
    articles = Article.published.select_related("category").order_by("-published_at")[:100]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for article in articles:
        parts.append(
            "<url><loc>{}</loc><news:news><news:publication>"
            "<news:name>{}</news:name><news:language>en</news:language>"
            "</news:publication><news:publication_time>{}</news:publication_time>"
            "<news:title>{}</news:title></news:news>".format(
                xml_escape(settings.SITE_URL + article.get_absolute_url()),
                xml_escape(settings.SITE_NAME),
                article.published_at.strftime("%Y-%m-%dT%H:%M:%S+03:00"),
                xml_escape(article.title),
            )
        )
        if article.image_url:
            parts.append("<image:image><image:loc>{}</image:loc></image:image>".format(xml_escape(article.image_url)))
        parts.append("</url>")
    parts.append("</urlset>")
    return HttpResponse("".join(parts), content_type="application/xml")


def rss_feed(request):
    articles = Article.published.select_related("category", "author__user").order_by("-published_at")[:30]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        f"<title>{xml_escape(settings.SITE_NAME)}</title>",
        f"<link>{settings.SITE_URL}/</link>",
        f"<description>{xml_escape(settings.SITE_TAGLINE)}</description>",
        "<language>en-ke</language>",
    ]
    for article in articles:
        link = settings.SITE_URL + article.get_absolute_url()
        parts.append(
            "<item><title>{}</title><link>{}</link><guid>{}</guid>"
            "<pubDate>{}</pubDate><description>{}</description></item>".format(
                xml_escape(article.title),
                xml_escape(link),
                xml_escape(link),
                article.published_at.strftime("%a, %d %b %Y %H:%M:%S +0300"),
                xml_escape(article.excerpt or article.subtitle or ""),
            )
        )
    parts.append("</channel></rss>")
    return HttpResponse("".join(parts), content_type="application/rss+xml")


PAGES = {
    "about": {
        "title": "About Kericho Daily",
        "intro": "Your Trusted Source. Your Daily News.",
        "sections": [
            {
                "heading": "Who we are",
                "body": "Kericho Daily is an independent digital news platform for Kericho County, the wider South Rift, Kenya and the Kenyan diaspora. Our focus is original local reporting, clear context and stories that matter to the communities we serve.",
            },
            {
                "heading": "Our editorial promise",
                "body": "We prioritise accuracy, fairness, original reporting, right of reply, clear corrections and a firm separation between editorial and advertising. Sponsored content is always labelled. Unverified claims are not published as breaking news.",
            },
            {
                "heading": "Coverage",
                "body": "Local government, tea and agriculture, education, business, crime and security, politics, entertainment, sports, technology, lifestyle and community voices from Kericho Town, Ainamoi, Belgut, Bureti, Kipkelion East, Kipkelion West, Sigowet/Soin, Londiani, Litein, Kabianga and surrounding areas.",
            },
        ],
    },
    "privacy": {
        "title": "Privacy Policy",
        "intro": "How this demonstration website handles information.",
        "sections": [
            {"heading": "Information we collect", "body": "Newsletter subscriptions store the email address and optional name you provide. Comments store the name, email and message you submit for editorial moderation. Basic anonymised page-view data is stored for analytics."},
            {"heading": "How we use it", "body": "To deliver the newsletter, moderate comments, understand readership and improve the website. We do not sell personal information."},
            {"heading": "Your choices", "body": "You can unsubscribe from the newsletter using the link in any email, request deletion of a comment, or clear browser notification permissions at any time."},
            {"heading": "Cookies", "body": "We use a session cookie for login and security, and local storage for your dark-mode preference. Advertising partners may set their own cookies only where their scripts are explicitly configured."},
        ],
    },
    "terms": {
        "title": "Terms and Conditions",
        "intro": "Please read these terms before using the site.",
        "sections": [
            {"heading": "Use of content", "body": "Original reporting on this site is protected by copyright. You may link to our stories, but reproduction or reuse requires written permission. Articles labelled 'Sample report' are illustrative content and are not verified reporting."},
            {"heading": "Comments", "body": "Comments are moderated. Hate speech, personal attacks, defamatory claims, spam and unverified breaking-news claims will not be published."},
            {"heading": "Accuracy", "body": "We work to correct errors promptly and transparently. Articles clearly labelled 'Sample report' are illustrative and must not be republished as factual reporting."},
            {"heading": "External links", "body": "We are not responsible for the content of third-party websites, including social platforms and advertisers."},
        ],
    },
    "corrections": {
        "title": "Corrections and Editorial Policy",
        "intro": "Trust is built through transparency.",
        "sections": [
            {"heading": "Corrections", "body": "We correct errors promptly, keep a visible correction note on the affected article and record the date and reason for the change. Email corrections@kerichodaily.co.ke."},
            {"heading": "Verification", "body": "We verify facts with primary sources, seek comment from affected parties, distinguish reporting from opinion and label sponsored material clearly."},
            {"heading": "Sample content notice", "body": "Stories marked 'Sample report' are illustrative demonstrations of the platform. Claims in those articles should not be treated as verified information."},
        ],
    },
    "team": {
        "title": "Our Newsroom",
        "intro": "The journalists and editors behind the sample publication.",
        "sections": [],
    },
}


def about(request):
    return _render_page(request, "about")


def privacy(request):
    return _render_page(request, "privacy")


def terms(request):
    return _render_page(request, "terms")


def corrections(request):
    return _render_page(request, "corrections")


def team(request):
    page = PAGES["team"]
    journalists = Profile.objects.filter(is_journalist=True, show_on_team_page=True).select_related("user")
    return render(
        request,
        "team.html",
        {
            "page_title": f"{page['title']} | {settings.SITE_NAME}",
            "page_description": page["intro"],
            "page": page,
            "journalists": journalists,
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )


def _render_page(request, page_key):
    page = PAGES[page_key]
    return render(
        request,
        "static_page.html",
        {
            "page_title": f"{page['title']} | {settings.SITE_NAME}",
            "page_description": page["intro"],
            "page": page,
            "page_key": page_key,
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thank you for contacting us. Our newsroom will respond shortly.", extra_tags="contact-success")
            return redirect("news:contact")
    else:
        form = ContactForm()
    return render(
        request,
        "contact.html",
        {
            "page_title": f"Contact Us | {settings.SITE_NAME}",
            "page_description": "Contact the Kericho Daily editorial team.",
            "form": form,
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )


def advertise(request):
    placements = [
        {"name": "Header banner", "detail": "High-visibility placement above the fold on every page."},
        {"name": "Homepage sidebar", "detail": "Sticky sidebar unit beside the main news flow."},
        {"name": "Between article cards", "detail": "Native placement inside the latest-news grid."},
        {"name": "Inside article pages", "detail": "Top and inline units on long-form reading pages."},
        {"name": "Footer advertisement", "detail": "Wide placement at the end of every page."},
        {"name": "Mobile placements", "detail": "Responsive units optimised for Kenyan mobile networks."},
    ]
    return render(
        request,
        "advertise.html",
        {
            "page_title": f"Advertise With Us | {settings.SITE_NAME}",
            "page_description": "Reach readers across Kericho County, the South Rift and the Kenyan diaspora.",
            "placements": placements,
            "canonical_url": request.build_absolute_uri(request.path),
        },
    )
