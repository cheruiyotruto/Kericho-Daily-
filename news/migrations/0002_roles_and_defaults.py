from django.db import migrations

ROLE_SPECS = {
    "Super Administrator": {
        "article": ["add", "change", "delete", "view"],
        "category": ["add", "change", "delete", "view"],
        "locality": ["add", "change", "delete", "view"],
        "tag": ["add", "change", "delete", "view"],
        "comment": ["add", "change", "delete", "view"],
        "breakingnews": ["add", "change", "delete", "view"],
        "newslettersubscriber": ["add", "change", "delete", "view"],
        "advertisement": ["add", "change", "delete", "view"],
        "video": ["add", "change", "delete", "view"],
        "pageview": ["view"],
        "contactmessage": ["add", "change", "delete", "view"],
        "notificationsubscription": ["add", "change", "delete", "view"],
        "profile": ["add", "change", "delete", "view"],
    },
    "Managing Editor": {
        "article": ["add", "change", "delete", "view"],
        "category": ["add", "change", "delete", "view"],
        "locality": ["add", "change", "delete", "view"],
        "tag": ["add", "change", "delete", "view"],
        "comment": ["change", "delete", "view"],
        "breakingnews": ["add", "change", "delete", "view"],
        "newslettersubscriber": ["view"],
        "advertisement": ["view"],
        "video": ["add", "change", "delete", "view"],
        "pageview": ["view"],
        "contactmessage": ["change", "view"],
        "profile": ["change", "view"],
    },
    "News Editor": {
        "article": ["add", "change", "delete", "view"],
        "category": ["view"],
        "locality": ["view"],
        "tag": ["add", "change", "view"],
        "comment": ["change", "view"],
        "breakingnews": ["change", "view"],
        "video": ["add", "change", "view"],
        "pageview": ["view"],
        "profile": ["view"],
    },
    "Journalist/Reporter": {
        "article": ["add", "change", "view"],
        "category": ["view"],
        "locality": ["view"],
        "tag": ["view"],
        "video": ["view"],
        "profile": ["view"],
    },
    "Advertising Manager": {
        "advertisement": ["add", "change", "delete", "view"],
        "pageview": ["view"],
        "article": ["view"],
        "newslettersubscriber": ["view"],
        "contactmessage": ["view"],
    },
    "Moderator": {
        "comment": ["change", "delete", "view"],
        "article": ["view"],
        "contactmessage": ["change", "view"],
        "profile": ["view"],
    },
    "Subscriber": {
        "article": ["view"],
    },
}

PROFILE_ROLE_TO_GROUP = {
    "super_admin": "Super Administrator",
    "managing_editor": "Managing Editor",
    "news_editor": "News Editor",
    "journalist": "Journalist/Reporter",
    "advertising_manager": "Advertising Manager",
    "moderator": "Moderator",
    "subscriber": "Subscriber",
}


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    db = schema_editor.connection.alias

    for group_name, model_permissions in ROLE_SPECS.items():
        group, _ = Group.objects.using(db).get_or_create(name=group_name)
        permission_ids = []
        for model_name, actions in model_permissions.items():
            try:
                content_type = ContentType.objects.db_manager(db).get_by_natural_key("news", model_name)
            except ContentType.DoesNotExist:
                continue
            codenames = [f"{action}_{model_name}" for action in actions]
            permission_ids.extend(
                Permission.objects.using(db)
                .filter(content_type=content_type, codename__in=codenames)
                .values_list("id", flat=True)
            )
        group.permissions.set(permission_ids)


def sync_existing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    Profile = apps.get_model("news", "Profile")
    db = schema_editor.connection.alias
    for profile in Profile.objects.using(db).select_related("user"):
        group_name = PROFILE_ROLE_TO_GROUP.get(profile.role)
        if not group_name:
            continue
        group = Group.objects.using(db).filter(name=group_name).first()
        if group:
            profile.user.groups.add(group)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("news", "0001_initial")]

    operations = [
        migrations.RunPython(create_roles, noop),
        migrations.RunPython(sync_existing_profiles, noop),
    ]
