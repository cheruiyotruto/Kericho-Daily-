from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Profile


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = AuthenticationForm(request, data=request.POST or None)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f"Welcome back, {user.get_full_name() or user.get_username()}.")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("dashboard:home")
    if form.errors and request.method == "POST":
        messages.error(request, "Incorrect username or password. Please try again.")
    return render(
        request,
        "registration/login.html",
        {"form": form, "next": next_url, "page_title": "Sign in | KERICHO DAILY"},
    )


def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("news:home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("news:home")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        Profile.objects.get_or_create(user=user, defaults={"role": "subscriber"})
        login(request, user)
        messages.success(request, "Your account is ready. Welcome to Kericho Daily.")
        return redirect("news:home")
    return render(
        request,
        "registration/register.html",
        {"form": form, "page_title": "Create an account | KERICHO DAILY"},
    )


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(
        request,
        "registration/profile.html",
        {"profile": profile, "page_title": "My account | KERICHO DAILY"},
    )
