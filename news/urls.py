from django.urls import path

from . import views

app_name = "news"

urlpatterns = [
    path("", views.home, name="home"),
    path("category/<slug:slug>/", views.category, name="category"),
    path("locality/<slug:slug>/", views.locality, name="locality"),
    path("author/<slug:slug>/", views.author_profile, name="author"),
    path("tag/<slug:slug>/", views.tag_articles, name="tag"),
    path("search/", views.search, name="search"),
    path("videos/", views.videos, name="videos"),
    path("videos/<int:video_id>/", views.video_detail, name="video_detail"),
    path("newsletter/unsubscribe/<str:token>/", views.newsletter_unsubscribe, name="newsletter_unsubscribe"),
    path("comment/<int:article_id>/", views.comment_create, name="comment_create"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("advertise/", views.advertise, name="advertise"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("corrections/", views.corrections, name="corrections"),
    path("team/", views.team, name="team"),
    # SEO-friendly article URLs: /kericho-news/example-headline/
    path("<slug:category_slug>/<slug:slug>/", views.article_detail, name="article"),
]
