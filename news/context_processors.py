from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import Advertisement, BreakingNews, Category, Locality


def site_context(request):
    """Global template context: navigation, breaking news and site configuration."""
    categories = cache.get("nav_categories")
    if categories is None:
        categories = list(Category.objects.filter(show_in_nav=True).order_by("order", "name"))
        cache.set("nav_categories", categories, 300)

    localities = cache.get("county_localities")
    if localities is None:
        localities = list(Locality.objects.all().order_by("name"))
        cache.set("county_localities", localities, 600)

    breaking = cache.get("active_breaking")
    if breaking is None:
        breaking = list(
            BreakingNews.objects.filter(is_active=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now()))
            .select_related("article", "article__category")[:8]
        )
        cache.set("active_breaking", breaking, 60)

    return {
        "site_name": settings.SITE_NAME,
        "site_tagline": settings.SITE_TAGLINE,
        "site_url": settings.SITE_URL,
        "site_email": settings.SITE_EMAIL,
        "site_phone": settings.SITE_PHONE,
        "social_links": settings.SOCIAL_LINKS,
        "nav_categories": categories,
        "county_localities": localities,
        "breaking_items": breaking,
        "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
        "google_adsense_client": settings.GOOGLE_ADSENSE_CLIENT,
        "google_ad_manager_id": settings.GOOGLE_AD_MANAGER_ID,
        "search_console_verification": settings.SEARCH_CONSOLE_VERIFICATION,
        "show_demo_banner": settings.SHOW_DEMO_BANNER,
        "is_demo_site": settings.SHOW_DEMO_BANNER,
    }
