from django.urls import path

from . import accounts

app_name = "accounts"

urlpatterns = [
    path("login/", accounts.login_view, name="login"),
    path("logout/", accounts.logout_view, name="logout"),
    path("register/", accounts.register_view, name="register"),
    path("profile/", accounts.profile_view, name="profile"),
]
