"""Acesso: configuração inicial, login, PIN, aparelhos e senha (F-001; security-plan.md §3)."""

import time

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from apps.ledger import audit

from . import devices
from .forms import (
    ChangePasswordForm,
    ConfirmPasswordForm,
    DeviceForm,
    LoginForm,
    PinForm,
    SetupForm,
)
from .models import TrustedDevice

USERNAME = "usuario"  # sistema de usuário único


def _single_user():
    return get_user_model().objects.filter(username=USERNAME).first()


def _safe_next(request, default="ui:home"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, True):
        return target
    return default


def _start_session(request, user, method: str) -> None:
    request.session["auth_method"] = method
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    now = int(time.time())
    request.session["auth_started"] = now
    request.session["last_activity"] = now


@login_not_required
@require_http_methods(["GET", "POST"])
def setup(request):
    if _single_user():
        return redirect("security:login")
    form = SetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = get_user_model().objects.create_user(
            USERNAME, password=form.cleaned_data["password"]
        )
        audit.record_event("setup", "auth_user", user.pk)
        _start_session(request, user, "password")
        messages.success(request, "Senha criada. Bem-vindo!")
        return redirect("ui:home")
    return render(request, "security/setup.html", {"form": form})


@login_not_required
@require_http_methods(["GET", "POST"])
def login_view(request):
    if not _single_user():
        return redirect("security:setup")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, username=USERNAME, password=form.cleaned_data["password"])
        if user is not None:
            _start_session(request, user, "password")
            device = devices.find(request)
            if device:
                devices.renew(device)
            if form.cleaned_data["trust_device"] and not device:
                return redirect("security:device_new")
            return redirect(_safe_next(request))
        form.add_error("password", "Senha incorreta.")
    return render(request, "security/login.html", {"form": form, "next": _safe_next(request, "")})


@login_not_required
@require_http_methods(["GET", "POST"])
def pin_view(request):
    device = devices.find(request)
    if device is None:
        return redirect("security:login")
    form = PinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if devices.verify_pin(device, form.cleaned_data["pin"]):
            _start_session(request, device.user, "pin")
            return redirect(_safe_next(request))
        device.refresh_from_db()
        if device.revoked_at:
            messages.error(request, "PIN errado 5 vezes. Entre com a senha.")
            return redirect("security:login")
        form.add_error("pin", "PIN incorreto.")
    return render(
        request,
        "security/pin.html",
        {"form": form, "device": device, "next": _safe_next(request, "")},
    )


@require_http_methods(["GET", "POST"])
def device_new(request):
    if request.session.get("auth_method") != "password":
        messages.error(request, "Para confiar num aparelho, entre com a senha.")
        return redirect("security:login")
    form = DeviceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        _, token = devices.issue(
            request.user,
            name=form.cleaned_data["name"],
            pin=form.cleaned_data["pin"],
            user_agent=request.headers.get("User-Agent", ""),
        )
        response = redirect("ui:home")
        devices.set_cookie(response, token)
        messages.success(request, "Aparelho confiável ativado. Use o PIN nas próximas entradas.")
        return response
    return render(request, "security/device_new.html", {"form": form})


@require_http_methods(["GET"])
def settings_view(request):
    return render(
        request,
        "security/settings.html",
        {
            "devices": TrustedDevice.objects.filter(user=request.user).order_by("-created_at"),
            "current": devices.find(request),
            "confirm_form": ConfirmPasswordForm(),
            "password_form": ChangePasswordForm(),
        },
    )


def _password_ok(request) -> bool:
    form = ConfirmPasswordForm(request.POST)
    if form.is_valid() and request.user.check_password(form.cleaned_data["password"]):
        return True
    messages.error(request, "Senha incorreta. Nada foi alterado.")
    return False


@require_POST
def device_revoke(request, pk):
    if _password_ok(request):
        device = TrustedDevice.objects.filter(user=request.user, pk=pk).first()
        if device:
            devices.revoke(device, reason="revogado pelo usuário")
            messages.success(request, f"Aparelho “{device.name}” revogado.")
    return redirect("security:settings")


@require_POST
def device_revoke_all(request):
    if _password_ok(request):
        count = devices.revoke_all(request.user, reason="revogar todos")
        messages.success(request, f"{count} aparelho(s) revogado(s).")
    return redirect("security:settings")


@require_POST
def change_password(request):
    form = ChangePasswordForm(request.POST)
    if form.is_valid() and request.user.check_password(form.cleaned_data["current"]):
        request.user.set_password(form.cleaned_data["new"])
        request.user.save()
        update_session_auth_hash(request, request.user)
        devices.revoke_all(request.user, reason="troca de senha")
        audit.record_event("password_changed", "auth_user", request.user.pk)
        messages.success(request, "Senha trocada. Os aparelhos confiáveis foram revogados.")
    else:
        messages.error(request, "Não foi possível trocar a senha. Confira os campos.")
        for error in form.non_field_errors():
            messages.error(request, error)
    return redirect("security:settings")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("security:login")
