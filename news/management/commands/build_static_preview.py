"""Render a read-only static preview of the public site for GitHub Pages.

Interactive Django features (search, comments, newsletters, dashboard) are not
available on GitHub Pages. This command renders the public pages with the test
client, prefixes internal links for a project Pages site, and copies static
assets alongside the generated HTML.
"""

import os
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client

from news.models import Article, Category, Locality, Profile, Tag, Video


PAGES = [
    "/",
    "/videos/",
    "/about/",
    "/contact/",
    "/advertise/",
    "/privacy/",
    "/terms/",
    "/corrections/",
    "/team/",
    "/robots.txt",
    "/sitemap.xml",
    "/news-sitemap.xml",
    "/rss.xml",
]


class Command(BaseCommand):
    help = "Build a static preview of public pages in a GitHub Pages friendly layout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=os.getenv("STATIC_PREVIEW_ROOT", str(settings.BASE_DIR / "site-build")),
            help="Directory to write the static site into.",
        )
        parser.add_argument(
            "--prefix",
            default=os.getenv("STATIC_PREVIEW_PREFIX", "/Kericho-Daily-"),
            help="GitHub Pages project path prefix, e.g. /Kericho-Daily-.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"]).resolve()
        prefix = options["prefix"].rstrip("/")
        site_base = os.getenv(
            "SITE_URL", f"https://cheruiyotruto.github.io{prefix or ''}"
        ).rstrip("/")
        print(f"Building into {output} ({site_base})...", flush=True)

        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        print("Output directory prepared.", flush=True)

        static_source = settings.BASE_DIR / "static"
        if static_source.exists():
            shutil.copytree(static_source, output / "static", dirs_exist_ok=True)
        self.patch_javascript(output / "static" / "js" / "main.js", prefix)
        print("Static assets copied.", flush=True)

        paths = set(PAGES)
        paths.update(category.get_absolute_url() for category in Category.objects.all())
        paths.update(locality.get_absolute_url() for locality in Locality.objects.all())
        paths.update(
            profile.get_absolute_url()
            for profile in Profile.objects.filter(show_on_team_page=True)
        )
        paths.update(f"/tag/{tag.slug}/" for tag in Tag.objects.all())
        paths.update(f"/videos/{video.id}/" for video in Video.objects.all())
        paths.update(
            article.get_absolute_url()
            for article in Article.objects.filter(status="published")
        )

        client = Client()
        written = 0
        print(f"Rendering {len(paths)} paths...", flush=True)
        for path in sorted(paths):
            response = client.get(path)
            if response.status_code != 200:
                self.stderr.write(f"Skipping {path} (HTTP {response.status_code})")
                continue
            content = response.content.decode("utf-8")
            content = self.rewrite(content, prefix, site_base)
            relative = path.strip("/")
            if relative.endswith((".txt", ".xml")):
                target = output / relative
            else:
                target = output / relative / "index.html" if relative else output / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written += 1

        not_found = client.get("/__static_preview_missing__/")
        if not_found.status_code == 404:
            (output / "404.html").write_text(
                self.rewrite(not_found.content.decode("utf-8"), prefix, site_base),
                encoding="utf-8",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Static preview written to {output} ({written} pages, prefix {prefix or '/'})"
            )
        )

    @staticmethod
    def rewrite(content, prefix, site_base):
        pattern = r'(?P<attr>(?:href|src|action|data-url|data-next-url|poster))="/'
        content = re.sub(pattern, lambda m: f'{m.group("attr")}="{prefix}/', content)
        content = content.replace("http://testserver", site_base)
        content = content.replace("https://testserver", site_base)
        content = content.replace("http://localhost:8000", site_base)
        return content

    @staticmethod
    def patch_javascript(path, prefix):
        if not path.exists():
            return
        js = path.read_text(encoding="utf-8")
        js = js.replace(
            'fetch("/newsletter/subscribe/"',
            'fetch("data:application/json,%7B%22ok%22%3Afalse%2C%22message%22%3A%22Static%20preview%3A%20subscriptions%20are%20disabled.%22%7D"',
        )
        js = js.replace('if (notificationButton && "Notification" in window)', "if (false)")
        js = js.replace('fetch(`/ads/impression/', f'fetch(`{prefix}/ads/impression/')
        js = js.replace("if (loadMore) {", "if (false) {")
        path.write_text(js, encoding="utf-8")
