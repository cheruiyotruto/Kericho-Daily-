from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from news import views as news_views

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("dashboard/", include(("news.dashboard_urls", "dashboard"), namespace="dashboard")),
    path("accounts/", include(("news.accounts_urls", "accounts"), namespace="accounts")),
    path("health", news_views.health, name="health"),
    path("sw.js", news_views.service_worker, name="service_worker"),
    path("robots.txt", news_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", news_views.sitemap_xml, name="sitemap_xml"),
    path("news-sitemap.xml", news_views.news_sitemap_xml, name="news_sitemap_xml"),
    path("rss.xml", news_views.rss_feed, name="rss_feed"),
    path("ads/impression/<int:ad_id>/", news_views.ad_impression, name="ad_impression"),
    path("ads/click/<int:ad_id>/", news_views.ad_click, name="ad_click"),
    path("notifications/subscribe/", news_views.notification_subscribe, name="notification_subscribe"),
    path("newsletter/subscribe/", news_views.newsletter_subscribe, name="newsletter_subscribe"),
    path("", include(("news.urls", "news"), namespace="news")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "news.views.error_400"
handler403 = "news.views.error_403"
handler404 = "news.views.error_404"
handler500 = "news.views.error_500"
