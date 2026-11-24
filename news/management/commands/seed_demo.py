"""Populate Kericho Daily with clearly labelled demonstration content."""

from datetime import timedelta
import random
from textwrap import dedent

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from news.models import (
    Advertisement,
    Article,
    BreakingNews,
    Category,
    Comment,
    Locality,
    NewsletterSubscriber,
    PageView,
    Profile,
    Tag,
    Video,
)
from news.permissions import ROLE_RANK


CATEGORY_DATA = [
    ("kericho-news", "Kericho News", "#123B32", "Community, county government and local development stories from Kericho County."),
    ("kenya-news", "Kenya News", "#10243A", "National developments and public-interest reporting from across Kenya."),
    ("politics", "Politics", "#8E1B2E", "Governance, policy and political analysis with context."),
    ("business", "Business", "#0F5B4D", "Markets, entrepreneurship, tea, trade and the local economy."),
    ("education", "Education", "#2E5A88", "Schools, universities, exams and learning opportunities."),
    ("crime-security", "Crime & Security", "#6A3D9A", "Public safety and justice reporting, careful with unverified claims."),
    ("entertainment", "Entertainment", "#B3316A", "Kenyan music, film, culture and local talent."),
    ("sports", "Sports", "#C46210", "Football, athletics and community sport."),
    ("technology", "Technology", "#1D6E8B", "Digital tools, connectivity and innovation."),
    ("lifestyle", "Lifestyle", "#7A6A2B", "Health, travel, food, family and community life."),
    ("opinion", "Opinion", "#4A4A4A", "Clearly labelled analysis and commentary from contributors."),
]

LOCALITIES = [
    "Kericho Town", "Ainamoi", "Belgut", "Bureti", "Kipkelion East",
    "Kipkelion West", "Sigowet/Soin", "Londiani", "Litein", "Kabianga",
]

ACCOUNTS = [
    ("admin", "Admin@123", "Amina", "Admin", "super_admin", True, "Demonstration super administrator with full newsroom access."),
    ("editor", "Editor@123", "David", "Editor", "managing_editor", True, "Sample managing editor overseeing the demonstration newsroom."),
    ("newseditor", "News@123", "Wanjiku", "Njoroge", "news_editor", True, "Sample news editor responsible for planning and publication."),
    ("reporter", "Reporter@123", "Brian", "Kiptoo", "journalist", True, "Sample reporter covering Kericho Town, Ainamoi and community stories."),
    ("moderator", "Moderator@123", "Faith", "Chebet", "moderator", False, "Sample moderator responsible for reader comment review."),
    ("ads", "Ads@123", "Peter", "Mwangi", "advertising_manager", False, "Sample advertising manager handling demonstration campaigns."),
]

GROUP_NAMES = {
    "super_admin": "Super Administrator",
    "managing_editor": "Managing Editor",
    "news_editor": "News Editor",
    "journalist": "Journalist/Reporter",
    "advertising_manager": "Advertising Manager",
    "moderator": "Moderator",
    "subscriber": "Subscriber",
}

IMAGES = {
    "newsroom": "https://images.unsplash.com/photo-1495020689067-958852a7765e?auto=format&fit=crop&w=1400&q=80",
    "broadcast": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1400&q=80",
    "landscape": "https://images.unsplash.com/photo-1523995462485-3d171b5c8fa9?auto=format&fit=crop&w=1400&q=80",
    "business": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1400&q=80",
    "education": "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?auto=format&fit=crop&w=1400&q=80",
    "policy": "https://images.unsplash.com/photo-1487958449943-2429e8be8625?auto=format&fit=crop&w=1400&q=80",
    "community": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1400&q=80",
    "farm": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1400&q=80",
    "road": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?auto=format&fit=crop&w=1400&q=80",
    "concert": "https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=1400&q=80",
    "sports": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=1400&q=80",
    "tech": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1400&q=80",
    "lifestyle": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=1400&q=80",
    "opinion": "https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=1400&q=80",
    "data": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1400&q=80",
}

ARTICLES = [
    ("SAMPLE: How a county budget is drafted — a citizen's guide", "kericho-news", "newsroom", ["Kericho Town", "Ainamoi"], "county government, budget", 0, 1842, True, False),
    ("SAMPLE: Tea traceability and the smallholder farmer", "business", "farm", ["Kericho Town", "Belgut"], "tea farming, agriculture", 1, 1298, True, False),
    ("SAMPLE: A field guide to covering local elections fairly", "politics", "policy", ["Litein", "Kabianga"], "elections, governance", 1, 964, False, False),
    ("SAMPLE: Inside a school improvement meeting", "education", "education", ["Bureti", "Kipkelion East"], "schools, education", 2, 742, False, False),
    ("SAMPLE: What responsible crime reporting looks like", "crime-security", "broadcast", ["Kericho Town"], "public safety, ethics", 2, 611, False, False),
    ("SAMPLE: Local musicians and the digital stage", "entertainment", "concert", ["Kericho Town"], "music, local talent", 3, 1104, False, False),
    ("SAMPLE: Athletics talent development in the South Rift", "sports", "sports", ["Kipkelion West", "Londiani"], "athletics, sport", 3, 887, False, False),
    ("SAMPLE: Affordable smartphones and mobile news consumption", "technology", "tech", ["Kericho Town"], "mobile, technology", 4, 534, False, False),
    ("SAMPLE: Community markets and the local economy", "kericho-news", "community", ["Litein", "Sigowet/Soin"], "markets, business", 4, 698, False, False),
    ("SAMPLE: Reading a ward development plan without jargon", "kenya-news", "data", ["Ainamoi"], "devolution, analysis", 5, 462, False, False),
    ("SAMPLE: Road safety around school terms", "kenya-news", "road", ["Londiani", "Kabianga"], "roads, safety", 5, 392, False, False),
    ("SAMPLE: How newsrooms verify a viral video", "technology", "broadcast", ["Kericho Town"], "verification, media", 6, 755, False, False),
    ("SAMPLE: A beginner's guide to personal finance", "business", "business", ["Kericho Town"], "finance, small business", 6, 418, False, False),
    ("SAMPLE: Preserving family stories across generations", "lifestyle", "lifestyle", ["Bureti"], "family, culture", 7, 305, False, False),
    ("SAMPLE: Why editorial independence matters", "opinion", "opinion", ["Kericho Town"], "editorial policy, opinion", 7, 521, False, False),
    ("SAMPLE: Questions to ask before sharing a health claim", "lifestyle", "data", ["Ainamoi"], "health, verification", 8, 367, False, False),
    ("SAMPLE: The anatomy of a good interview", "kenya-news", "newsroom", ["Kericho Town"], "journalism, interviews", 9, 289, False, False),
    ("SAMPLE: What a corrections note should contain", "opinion", "opinion", ["Kericho Town"], "corrections, transparency", 10, 244, False, False),
]


def body_for(title, subtitle, category_name):
    return dedent(
        f"""
        <p><strong>This is demonstration copy.</strong> The sample story below shows how a {category_name.lower()} article would be structured by a professional newsroom. It is not a report about a real event.</p>
        <p>{subtitle} In a live publication, this section would summarise the verified finding and explain why it matters to readers in Kericho County, the wider South Rift and the Kenyan diaspora.</p>
        <h2>What the newsroom would verify</h2>
        <p>Reporters would start with primary documents, direct interviews and on-the-record comment. Every claim would be checked before publication, and affected parties would be given a fair opportunity to respond. Where information remains unconfirmed, the story would say so plainly.</p>
        <ul><li>Confirm the date, location and people involved.</li><li>Check documents against independent sources.</li><li>Seek comment from those affected.</li><li>Separate verified facts from analysis or opinion.</li></ul>
        <h2>Why this matters locally</h2>
        <p>For readers in Kericho Town, Ainamoi, Belgut, Bureti, Kipkelion, Sigowet/Soin, Londiani, Litein and Kabianga, clear reporting helps communities understand decisions that affect schools, roads, farms, businesses and public services.</p>
        <blockquote>Good journalism does not rush to fill a headline. It earns the reader's trust through accuracy, context and accountability.</blockquote>
        <p>Advertising would never influence this editorial judgement. Sponsored material would carry a visible label, and corrections would be published transparently beside the original story.</p>
        <h2>How to follow the next update</h2>
        <p>Subscribe to the sample newsletter, follow the category page for new reporting and share verified tips with the editorial desk. Again: <em>this article is sample content and must not be republished as factual news.</em></p>
        """
    )


class Command(BaseCommand):
    help = "Seed the database with labelled sample content, demo accounts and ad campaigns."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo content before seeding (does not remove users).")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Article.objects.all().delete()
            Advertisement.objects.all().delete()
            BreakingNews.objects.all().delete()
            Video.objects.all().delete()
            Comment.objects.all().delete()
            PageView.objects.all().delete()
            NewsletterSubscriber.objects.all().delete()

        self.stdout.write("Creating categories and localities...")
        categories = {}
        for order, (slug, name, color, description) in enumerate(CATEGORY_DATA):
            category, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "color": color, "description": description, "order": order},
            )
            categories[slug] = category

        localities = {}
        for name in LOCALITIES:
            locality, _ = Locality.objects.get_or_create(
                slug=slugify(name), defaults={"name": name, "description": f"Sample local news coverage for {name} and nearby communities."}
            )
            localities[name] = locality

        self.stdout.write("Creating demo newsroom accounts and groups...")
        profiles = {}
        for username, password, first, last, role, is_journalist, bio in ACCOUNTS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "first_name": first, "last_name": last},
            )
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = role == "super_admin"
            user.is_active = True
            user.first_name = first
            user.last_name = last
            user.email = f"{username}@example.com"
            user.save()

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.is_journalist = is_journalist
            profile.bio = bio
            profile.show_on_team_page = is_journalist
            profile.save()
            profiles[username] = profile

            group = Group.objects.filter(name=GROUP_NAMES[role]).first()
            if group:
                user.groups.add(group)

        author_cycle = [profiles["reporter"], profiles["newseditor"], profiles["editor"], profiles["reporter"]]

        self.stdout.write("Creating sample articles...")
        created_articles = []
        for index, (title, cat_slug, image_key, area_names, tag_text, days_ago, views, featured, breaking) in enumerate(ARTICLES):
            slug = slugify(title)
            subtitle = "A demonstration article explaining process, context and editorial standards — not a verified news event."
            defaults = {
                "title": title,
                "subtitle": subtitle,
                "excerpt": f"Sample coverage of {cat_slug.replace('-', ' ')} with an emphasis on accuracy, context and public interest.",
                "body": body_for(title, subtitle, categories[cat_slug].name),
                "category": categories[cat_slug],
                "author": author_cycle[index % len(author_cycle)],
                "featured_image_url": IMAGES[image_key],
                "image_caption": "Illustrative image used for demonstration purposes.",
                "image_credit": "Kericho Daily demo / Unsplash",
                "status": "published",
                "published_at": timezone.now() - timedelta(days=days_ago, hours=index % 6),
                "is_featured": featured,
                "is_breaking": breaking,
                "is_sample": True,
                "views_count": views,
                "seo_title": f"{title} | Kericho Daily Sample Newsroom",
                "seo_description": subtitle,
                "focus_keyword": tag_text,
            }
            article, created = Article.objects.get_or_create(slug=slug, defaults=defaults)
            if not created:
                # Keep repeat runs idempotent without overwriting an editor's work.
                created_articles.append(article)
                continue

            article.localities.set([localities[name] for name in area_names if name in localities])
            tags = []
            for tag_name in [t.strip() for t in tag_text.split(",")]:
                tag, _ = Tag.objects.get_or_create(slug=slugify(tag_name), defaults={"name": tag_name.title()})
                tags.append(tag)
            article.tags.set(tags)
            created_articles.append(article)

        if created_articles:
            self.stdout.write("Creating sample comments and readership statistics...")
            first = created_articles[0]
            Comment.objects.get_or_create(
                article=first, name="Sample Reader", email="reader@example.com",
                body="This is a sample moderated comment showing how the discussion section would work.",
                defaults={"is_approved": True},
            )
            Comment.objects.get_or_create(
                article=created_articles[1], name="Demo Subscriber", email="subscriber@example.com",
                body="Demonstration comment awaiting editorial moderation. Not a real reader submission.",
                defaults={"is_approved": False},
            )

            random.seed(42)
            page_views = []
            for article in created_articles[:12]:
                for i in range(random.randint(8, 30)):
                    page_views.append(
                        PageView(
                            article=article,
                            path=article.get_absolute_url(),
                            viewer_key=f"demo-visitor-{random.randint(1, 120)}",
                            referrer=random.choice([
                                "", "https://www.google.com/", "https://x.com/", "https://facebook.com/"
                            ]),
                            user_agent=random.choice([
                                "Mozilla/5.0 (Linux; Android 13) Mobile",
                                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile",
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                            ]),
                            created_at=timezone.now() - timedelta(days=random.randint(0, 9), hours=random.randint(0, 20)),
                        )
                    )
            if not PageView.objects.exists():
                PageView.objects.bulk_create(page_views, batch_size=200)

        self.stdout.write("Creating breaking news ticker items...")
        ticker_items = [
            "SAMPLE DEMO: The newsroom dashboard can publish breaking alerts with moderation controls.",
            "SAMPLE DEMO: All headlines on this site are illustrative — not verified breaking news.",
            "SAMPLE DEMO: Readers can enable breaking-news notifications with consent.",
        ]
        for priority, headline in enumerate(ticker_items, start=1):
            BreakingNews.objects.get_or_create(headline=headline, defaults={"is_active": True, "priority": priority})

        self.stdout.write("Creating video entries...")
        videos = [
            ("SAMPLE: How a local newsroom verifies a story", "A walkthrough of verification steps for community reporters.", "M7lc1UVf-VE", "06:12", True),
            ("SAMPLE: Meeting the reporters behind the county desk", "A sample interview format for journalist profiles.", "aqz-KE-bpKQ", "09:45", False),
            ("SAMPLE: Community reporting from the South Rift", "A demonstration of short-form community video reporting.", "YE7VzlLtp-4", "04:30", False),
        ]
        for title, description, youtube_id, duration, featured in videos:
            Video.objects.get_or_create(
                youtube_id=youtube_id,
                defaults={
                    "title": title, "description": description, "category": categories["kenya-news"],
                    "duration": duration, "is_featured": featured, "is_sample": True,
                    "views": random.randint(120, 900), "published_at": timezone.now() - timedelta(days=random.randint(1, 12)),
                },
            )

        self.stdout.write("Creating demonstration advertising campaigns...")
        ads = [
            ("Sample Header Banner", "Example Business", "header", "image", IMAGES["business"], 10, None),
            ("Sample Homepage Sidebar", "South Rift Ventures (sample)", "homepage_sidebar", "image", IMAGES["farm"], 8, None),
            ("Sample In-Feed Promotion", "Demo Partner", "between_cards", "image", IMAGES["community"], 6, None),
            ("Sample Article Sponsor", "Example Retail", "article_top", "image", IMAGES["lifestyle"], 5, None),
            ("Sample Mobile Unit", "Demo Mobile Brand", "mobile_banner", "image", IMAGES["tech"], 4, None),
            ("AdSense demo slot", "Google AdSense", "footer", "adsense", "", 3, "1234567890"),
            ("Ad Manager demo slot", "Google Ad Manager", "article_inline", "ad_manager", "", 2, "kericho-inline"),
        ]
        for name, advertiser, placement, ad_type, image_url, priority, slot in ads:
            Advertisement.objects.get_or_create(
                name=name,
                defaults={
                    "advertiser": advertiser, "placement": placement, "ad_type": ad_type,
                    "image_url": image_url, "link_url": "https://example.com/",
                    "ad_slot": slot or "", "is_active": True, "priority": priority,
                    "campaign_start": timezone.now() - timedelta(days=10),
                    "campaign_end": timezone.now() + timedelta(days=60),
                    "budget": 45000 + (priority * 5000),
                    "impressions": random.randint(1200, 9000),
                    "clicks": random.randint(30, 300),
                },
            )

        self.stdout.write("Creating sample newsletter subscribers...")
        for i in range(1, 16):
            NewsletterSubscriber.objects.get_or_create(
                email=f"sample.reader{i}@example.com",
                defaults={"name": f"Sample Reader {i}", "is_active": i < 13, "source": "seed_demo"},
            )

        self.stdout.write(self.style.SUCCESS("Demo seeding complete."))
        self.stdout.write("Demo logins:")
        for username, password, *_ in ACCOUNTS:
            self.stdout.write(f"  {username:12s} / {password}")
