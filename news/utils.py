"""Small utilities for sanitising editorial HTML and calculating reading time."""

from html import escape, unescape
from html.parser import HTMLParser
import re

ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "blockquote", "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tr", "th", "td", "hr", "code", "pre",
}

VOID_TAGS = {"br", "hr", "img"}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "blockquote": {"cite"},
    "table": {"border"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


def _safe_url(value: str) -> bool:
    value = (value or "").strip().lower()
    if not value:
        return False
    if value.startswith(("/", "#", "mailto:", "tel:")):
        return True
    return value.startswith(("http://", "https://"))


class _EditorialSanitizer(HTMLParser):
    """Allow a conservative subset of editorial HTML and escape everything else."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.open_tags = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return

        clean = []
        for key, value in attrs:
            key = (key or "").lower()
            if key not in ALLOWED_ATTRIBUTES.get(tag, set()):
                continue
            value = unescape(value or "")
            if key in {"href", "src", "cite"} and not _safe_url(value):
                continue
            clean.append(f'{key}="{escape(value, quote=True)}"')

        if tag == "a" and 'rel="noopener noreferrer"' not in clean:
            clean.append('rel="noopener noreferrer"')
        if tag == "img":
            if 'loading="lazy"' not in clean:
                clean.append('loading="lazy"')

        attrs_text = (" " + " ".join(clean)) if clean else ""
        self.parts.append(f"<{tag}{attrs_text}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS and self.open_tags and self.open_tags[-1] == tag:
            self.open_tags.pop()
            if self.parts:
                self.parts.pop()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form", "svg"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        if tag in VOID_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                current = self.open_tags.pop()
                self.parts.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(escape(data))

    def handle_entityref(self, name):
        if not self.skip_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip_depth:
            self.parts.append(f"&#{name};")

    def result(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_editorial_html(value: str) -> str:
    if not value:
        return ""
    parser = _EditorialSanitizer()
    parser.feed(str(value))
    return parser.result().strip()


def plain_text(value: str) -> str:
    value = re.sub(r"<script.*?</script>|<style.*?</style>", " ", str(value or ""), flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def reading_time_minutes(value: str, words_per_minute: int = 220) -> int:
    words = len(plain_text(value).split())
    return max(1, (words + words_per_minute - 1) // words_per_minute)


def slugify_unique(model, source: str, exclude_pk=None, max_attempts: int = 50) -> str:
    """Generate a unique slug for a model, appending -2, -3 etc. when needed."""
    from django.utils.text import slugify

    base = slugify(source)[:160] or "item"
    candidate = base
    for attempt in range(2, max_attempts + 1):
        query = model.objects.filter(slug=candidate)
        if exclude_pk:
            query = query.exclude(pk=exclude_pk)
        if not query.exists():
            return candidate
        candidate = f"{base[:150]}-{attempt}"
    return f"{base[:140]}-{os_random_suffix()}"


def os_random_suffix() -> str:
    import secrets

    return secrets.token_hex(3)
