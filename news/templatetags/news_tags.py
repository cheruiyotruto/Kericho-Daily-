from datetime import timedelta

from django import template
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from news.models import Advertisement

register = template.Library()


@register.inclusion_tag("includes/ad.html", takes_context=True)
def ad_for_placement(context, placement):
    cache_key = f"active-ad-{placement}"
    ad = cache.get(cache_key)
    if ad is None:
        ad = (
            Advertisement.objects.filter(placement=placement, is_active=True)
            .filter(Q(campaign_start__isnull=True) | Q(campaign_start__lte=timezone.now()))
            .filter(Q(campaign_end__isnull=True) | Q(campaign_end__gte=timezone.now()))
            .order_by("-priority", "-created_at")
            .first()
        )
        cache.set(cache_key, ad, 120)
    return {
        "ad": ad,
        "placement": placement,
        "adsense_client": settings.GOOGLE_ADSENSE_CLIENT,
        "ad_manager_id": settings.GOOGLE_AD_MANAGER_ID,
        "request": context.get("request"),
    }


@register.simple_tag
def reading_time(article):
    return getattr(article, "reading_time", 1)


@register.filter
def short_date(value):
    if not value:
        return ""
    return value.strftime("%b %d, %Y")


@register.filter
def time_label(value):
    if not value:
        return ""
    diff = timezone.now() - value
    if diff < timedelta(minutes=1):
        return "just now"
    if diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() // 60)
        return f"{minutes} min ago"
    if diff < timedelta(days=1):
        hours = int(diff.total_seconds() // 3600)
        return f"{hours} hr ago"
    if diff < timedelta(days=7):
        days = diff.days
        return f"{days} day{'s' if days != 1 else ''} ago"
    return value.strftime("%d %b %Y")


@register.simple_tag
def page_url(request, page_number):
    if not request:
        return f"?page={page_number}"
    params = request.GET.copy()
    params["page"] = page_number
    return "?" + params.urlencode()


@register.simple_tag
def param_url(request, key, value):
    if not request:
        return f"?{key}={value}"
    params = request.GET.copy()
    params[key] = value
    if key != "page":
        params.pop("page", None)
    return "?" + params.urlencode()
