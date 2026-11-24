from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

ROLE_RANK = {
    "subscriber": 0,
    "moderator": 1,
    "advertising_manager": 1,
    "journalist": 2,
    "news_editor": 3,
    "managing_editor": 4,
    "super_admin": 5,
}

EDITORIAL_ROLES = {"super_admin", "managing_editor", "news_editor", "journalist"}
SENIOR_EDITOR_ROLES = {"super_admin", "managing_editor", "news_editor"}
AD_ROLES = {"super_admin", "advertising_manager"}
MODERATION_ROLES = {"super_admin", "managing_editor", "moderator"}


def current_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "super_admin"
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def has_role(user, roles):
    role = current_role(user)
    if not role:
        return False
    if role in roles:
        return True
    return ROLE_RANK.get(role, 0) >= max((ROLE_RANK.get(r, 0) for r in roles), default=0)


def is_staff_user(user):
    return bool(user and user.is_authenticated and (user.is_staff or current_role(user)))


def is_editorial(user):
    return is_staff_user(user) and has_role(user, EDITORIAL_ROLES)


def is_senior_editor(user):
    return is_staff_user(user) and has_role(user, SENIOR_EDITOR_ROLES)


def is_ad_manager(user):
    return is_staff_user(user) and has_role(user, AD_ROLES)


def is_moderator(user):
    return is_staff_user(user) and has_role(user, MODERATION_ROLES)


def staff_required(view_func=None, role_check=is_staff_user):
    def decorator(func):
        @wraps(func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not role_check(request.user):
                from django.contrib import messages

                messages.error(request, "You do not have permission to access that area.")
                return redirect("news:home")
            return func(request, *args, **kwargs)

        return wrapped

    if view_func:
        return decorator(view_func)
    return decorator
