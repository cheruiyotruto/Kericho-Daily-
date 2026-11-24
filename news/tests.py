from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Article, Category, NewsletterSubscriber, Profile


class NewsSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Kericho News", slug="kericho-news", color="#123B32")
        cls.user = User.objects.create_user(username="editor", password="Editor@123", is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=cls.user)
        profile.role = "managing_editor"
        profile.is_journalist = True
        profile.save()
        cls.article = Article.objects.create(
            title="SAMPLE: A demonstration story for Kericho",
            slug="sample-demonstration-story",
            subtitle="Sample subtitle",
            excerpt="Sample excerpt for the archive.",
            body="<p>This is sample article body text used for testing the reading interface and sanitisation.</p>",
            category=cls.category,
            author=profile,
            status="published",
            published_at=timezone.now(),
            is_sample=True,
        )

    def test_homepage_renders(self):
        response = self.client.get(reverse("news:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KERICHO DAILY")
        self.assertContains(response, "Latest News")

    def test_article_page_renders_with_seo(self):
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "newsarticle-schema")
        self.assertContains(response, "Share")
        self.assertEqual(Article.objects.get(pk=self.article.pk).views_count, 1)

    def test_category_and_search(self):
        self.assertEqual(self.client.get(self.category.get_absolute_url()).status_code, 200)
        response = self.client.get(reverse("news:search"), {"q": "demonstration"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SAMPLE: A demonstration story for Kericho")

    def test_static_and_seo_endpoints(self):
        for name in ["about", "contact", "advertise", "privacy", "terms", "corrections", "team", "videos"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"news:{name}")).status_code, 200)
        self.assertEqual(self.client.get(reverse("robots_txt")).status_code, 200)
        self.assertEqual(self.client.get(reverse("sitemap_xml")).status_code, 200)
        self.assertEqual(self.client.get(reverse("news_sitemap_xml")).status_code, 200)
        self.assertEqual(self.client.get(reverse("rss_feed")).status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/"))

    def test_dashboard_renders_for_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsroom overview")

    def test_dashboard_article_creation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("dashboard:article_new"),
            {
                "title": "SAMPLE: Another demonstration report",
                "subtitle": "Subtitle",
                "excerpt": "Excerpt",
                "body": "<p>A sufficiently long sample body for the dashboard form validation to accept this article as a demonstration.</p>",
                "category": self.category.pk,
                "status": "draft",
                "tag_list": "sample, demo",
                "seo_title": "",
                "seo_description": "",
                "canonical_url": "",
                "focus_keyword": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Article.objects.filter(slug="sample-another-demonstration-report").exists())

    def test_newsletter_subscription(self):
        response = self.client.post(
            reverse("newsletter_subscribe"),
            {"email": "reader@example.com", "name": "Reader"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(NewsletterSubscriber.objects.filter(email="reader@example.com").exists())
