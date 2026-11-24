from django.urls import path

from . import dashboard

app_name = "dashboard"

urlpatterns = [
    path("", dashboard.home, name="home"),
    path("articles/", dashboard.article_list, name="article_list"),
    path("articles/new/", dashboard.article_edit, name="article_new"),
    path("articles/<int:article_id>/edit/", dashboard.article_edit, name="article_edit"),
    path("articles/<int:article_id>/delete/", dashboard.article_delete, name="article_delete"),
    path("comments/", dashboard.comments, name="comments"),
    path("comments/<int:comment_id>/approve/", dashboard.comment_moderate, {"action": "approve"}, name="comment_approve"),
    path("comments/<int:comment_id>/reject/", dashboard.comment_moderate, {"action": "reject"}, name="comment_reject"),
    path("breaking/", dashboard.breaking, name="breaking"),
    path("breaking/<int:item_id>/toggle/", dashboard.breaking_toggle, name="breaking_toggle"),
    path("breaking/new/", dashboard.breaking_create, name="breaking_new"),
    path("breaking/<int:item_id>/delete/", dashboard.breaking_delete, name="breaking_delete"),
    path("advertisements/", dashboard.advertisements, name="advertisements"),
    path("advertisements/new/", dashboard.advertisement_edit, name="ad_new"),
    path("advertisements/<int:ad_id>/edit/", dashboard.advertisement_edit, name="ad_edit"),
    path("subscribers/", dashboard.subscribers, name="subscribers"),
    path("subscribers/export/", dashboard.subscribers_export, name="subscribers_export"),
    path("journalists/", dashboard.journalists, name="journalists"),
    path("journalists/<int:profile_id>/edit/", dashboard.journalist_edit, name="journalist_edit"),
    path("videos/", dashboard.videos, name="videos"),
    path("videos/new/", dashboard.video_edit, name="video_new"),
    path("videos/<int:video_id>/edit/", dashboard.video_edit, name="video_edit"),
    path("analytics/", dashboard.analytics, name="analytics"),
    path("messages/", dashboard.contact_messages, name="messages"),
]
