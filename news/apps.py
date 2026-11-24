from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "news"
    verbose_name = "Kericho Daily Newsroom"

    def ready(self):
        # Import signal handlers when the app registry is ready.
        from . import signals  # noqa: F401
