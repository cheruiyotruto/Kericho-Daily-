"""Import current headlines and breaking news from public RSS feeds.

The static GitHub Pages preview is rebuilt from a fresh database on every run,
so this command pulls recent headlines, stores them with source attribution and
creates breaking-news ticker entries. It never copies full article bodies.
"""

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from news.models import Article, BreakingNews, Category, Locality, Profile, Tag


FEEDS = [
    ("Kericho County", "Kericho County when:7d"),
    ("Kenya news", "Kenya news when:3d"),
    ("Breaking news", "Kenya breaking news when:2d"),
    ("Current affairs", "Kenya current affairs when:7d"),
    ("Africa", "Africa current affairs when:3d"),
]

CATEGORY_KEYWORDS = {
    "kericho-news": (
        "kericho", "kipkelion", "belgut", "londiani", "litein", "ainamoi",
        "bureti", "kabianga", "sigowet", "south rift",
    ),
    "politics": (
        "governor", "senator", "election", "politics", "odm", "uzda",
        "county assembly", "impeach", "president", "deputy president",
    ),
    "business": (
        "business", "economy", "tea", "market", "shilling", "investor",
        "road", "sgr", "housing", "trade", "tariff", "bank",
    ),
    "education": ("school", "kcse", "education", "university", "student", "teacher", "stem"),
    "crime-security": ("police", "crime", "security", "court", "arrest", "prison", "inmate"),
    "sports": ("sport", "football", "athletics", "tournament", "match", "celtic"),
    "entertainment": ("music", "film", "entertainment", "musician", "artist"),
    "technology": ("technology", "smartphone", "digital", "artificial intelligence", "mobile"),
    "lifestyle": ("health", "hospital", "weather", "rain", "family", "farm", "nurse"),
    "opinion": ("opinion", "analysis", "commentary", "editorial"),
}

TAG_STRIP = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")


class Command(BaseCommand):
    help = "Import recent current-affairs headlines and breaking news with source attribution."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            type=Path,
            help="Read RSS XML from a local file instead of fetching Google News.",
        )
        parser.add_argument("--limit", type=int, default=24, help="Maximum articles to import.")
        parser.add_argument("--max-age-days", type=int, default=10, help="Ignore older headlines.")

    def handle(self, *args, **options):
        fixtures = options["fixture"]
        items = []
        if fixtures:
            items.extend(self.parse_feed(fixtures.read_text(encoding="utf-8"), "Local fixture"))
        else:
            for label, query in FEEDS:
                url = (
                    "https://news.google.com/rss/search?q="
                    + urllib.parse.quote(query)
                    + "&hl=en-KE&gl=KE&ceid=KE:en"
                )
                try:
                    request = urllib.request.Request(
                        url, headers={"User-Agent": "KerichoDailyPreview/1.0"}
                    )
                    with urllib.request.urlopen(request, timeout=25) as response:
                        items.extend(self.parse_feed(response.read().decode("utf-8", "replace"), label))
                except Exception as exc:  # keep the build alive if one feed is unavailable
                    self.stderr.write(f"Feed unavailable ({label}): {exc}")

        cutoff = timezone.now() - timedelta(days=options["max_age_days"])
        clean = []
        seen = set()
        for item in items:
            published = item["published_at"]
            if not published or published < cutoff:
                continue
            if "\ufffd" in item["title"] or item["title"].count("??") > 2:
                continue
            if item["source_name"].lower() == "facebook":
                continue
            if not item["link"] or item["link"] in seen:
                continue
            if Article.objects.filter(source_url=item["link"]).exists():
                continue
            seen.add(item["link"])
            clean.append(item)

        clean.sort(key=lambda item: item["published_at"], reverse=True)
        clean = clean[: options["limit"]]
        if not clean:
            self.stdout.write("No new current headlines to import.")
            return

        author = self.get_wire_author()
        wire_tag, _ = Tag.objects.get_or_create(name="Wire update", defaults={"slug": "wire-update"})
        categories = {category.slug: category for category in Category.objects.all()}
        imported = []

        for item in clean:
            category_slug = self.categorise(item["title"])
            category = categories.get(category_slug) or Category.objects.first()
            if category is None:
                break
            slug = self.unique_slug(item["title"])
            excerpt = item["excerpt"] or f"{item['source_name']} reports: {item['title']}"
            body = (
                f"<p>{html.escape(excerpt)}</p>"
                f'<p><a href="{html.escape(item["link"], quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">Read the full report from {html.escape(item["source_name"])}</a>.</p>'
                "<p><em>This is an automatically imported headline and summary. Kericho Daily "
                "does not reproduce the full article; all rights remain with the original publisher.</em></p>"
            )
            article = Article.objects.create(
                title=item["title"][:240],
                slug=slug,
                subtitle=f"{item['source_name']} · Imported headline",
                excerpt=excerpt[:600],
                body=body,
                category=category,
                author=author,
                status="published",
                published_at=item["published_at"],
                is_sample=False,
                is_breaking=len(imported) < 6,
                is_featured=len(imported) < 4,
                source_url=item["link"],
                source_name=item["source_name"][:120],
                allow_comments=False,
            )
            article.tags.add(wire_tag)
            if category_slug == "kericho-news":
                locality = Locality.objects.filter(name__icontains="Kericho Town").first()
                if locality:
                    article.localities.add(locality)
            imported.append(article)

        # Refresh the breaking-news ticker with only the newest imported headlines.
        BreakingNews.objects.filter(link__startswith="https://news.google.com/").delete()
        for priority, article in enumerate(imported[:6], start=1):
            BreakingNews.objects.create(
                headline=f"{article.title} — {article.source_name}",
                article=article,
                link=article.source_url,
                priority=priority,
                expires_at=timezone.now() + timedelta(days=2),
            )

        # Keep the preview current by removing stale imported headlines.
        stale = (
            Article.objects.exclude(source_url="")
            .exclude(source_url__isnull=True)
            .filter(published_at__lt=cutoff)
        )
        stale_count = stale.count()
        stale.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(imported)} current headlines; removed {stale_count} stale items."
            )
        )

    @staticmethod
    def parse_feed(xml_text, label):
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError(f"invalid RSS from {label}: {exc}") from exc

        parsed = []
        for node in root.findall(".//item"):
            title = html.unescape((node.findtext("title") or "").strip())
            title = title.replace("\ufffd", "'")
            title = re.sub(r"(?<!\w)\?(?=\w)", "'", title)
            title = re.sub(r"(?<=\w)\?(?=\W|$)", "'", title)
            link = (node.findtext("link") or "").strip()
            source_node = node.find("source")
            source_name = (source_node.text if source_node is not None else "").strip() or "Original publisher"
            if not source_node or not (source_node.get("url") or "").startswith("http"):
                source_url = link
            else:
                source_url = source_node.get("url")
            if title.endswith(f" - {source_name}"):
                title = title[: -len(f" - {source_name}")].strip()
            description = SPACE.sub(" ", TAG_STRIP.sub(" ", html.unescape(node.findtext("description") or ""))).strip()
            published_at = None
            pub_date = node.findtext("pubDate")
            if pub_date:
                try:
                    published_at = parsedate_to_datetime(pub_date)
                    if timezone.is_naive(published_at):
                        published_at = timezone.make_aware(published_at, timezone.utc)
                except (TypeError, ValueError):
                    published_at = None
            parsed.append(
                {
                    "title": title,
                    "link": link or source_url,
                    "source_name": source_name,
                    "source_url": source_url,
                    "excerpt": description[:300],
                    "published_at": published_at,
                }
            )
        return parsed

    @staticmethod
    def categorise(title):
        lowered = title.lower()
        for slug, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return slug
        return "kenya-news"

    @staticmethod
    def unique_slug(title):
        base = slugify(title)[:200] or "current-headline"
        candidate = base
        counter = 2
        while Article.objects.filter(slug=candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base[: 200 - len(suffix)]}{suffix}"
            counter += 1
        return candidate

    @staticmethod
    def get_wire_author():
        user, created = User.objects.get_or_create(
            username="wire",
            defaults={
                "first_name": "Newsroom",
                "last_name": "Wire",
                "email": "wire@kerichodaily.co.ke",
                "is_staff": False,
                "is_superuser": False,
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        profile, _ = Profile.objects.get_or_create(
            user=user,
            defaults={
                "role": "news_editor",
                "is_journalist": True,
                "show_on_team_page": False,
                "bio": "Automated current-affairs desk. Imported headlines are attributed to their original publishers.",
            },
        )
        return profile
