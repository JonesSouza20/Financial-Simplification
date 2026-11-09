"""Tela de avisos em Ajustes (F-080)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from keyring.errors import KeyringError

from apps.backup import secrets
from apps.ledger import audit
from apps.ui import models as prefs

from . import services, telegram
from .forms import AlertSettingsForm
from .models import Notification


@require_http_methods(["GET", "POST"])
def alert_settings(request):
    start, end = services.quiet_hours()
    form = AlertSettingsForm(
        request.POST or None,
        initial={
            "chat_id": prefs.get(telegram.CHAT_KEY, ""),
            "days_before": services.days_before(),
            "quiet_start": start,
            "quiet_end": end,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if not request.user.check_password(data["password"]):
            form.add_error("password", "Senha incorreta. Nada foi alterado.")
        else:
            try:
                if data["token"]:
                    secrets.put(secrets.TELEGRAM_TOKEN, data["token"])
            except KeyringError:
                form.add_error(None, "Não foi possível gravar o token no cofre do Windows.")
            else:
                prefs.put(telegram.CHAT_KEY, data["chat_id"])
                prefs.put(services.DAYS_KEY, data["days_before"])
                prefs.put(services.QUIET_START_KEY, data["quiet_start"])
                prefs.put(services.QUIET_END_KEY, data["quiet_end"])
                audit.record_event(
                    "telegram_configured",
                    "setting",
                    0,
                    after={"token_changed": bool(data["token"])},
                )
                messages.success(
                    request, "Avisos salvos. Envie uma mensagem de teste para conferir."
                )
                return redirect("notifications:settings")
    return render(
        request,
        "notifications/settings.html",
        {
            "form": form,
            "has_token": secrets.has(secrets.TELEGRAM_TOKEN),
            "configured": telegram.configured(),
            "recent": Notification.objects.all()[:10],
        },
    )


@require_POST
def send_test(request):
    try:
        telegram.send("Teste do sistema Finanças: os avisos vão chegar aqui.")
        messages.success(request, "Mensagem de teste enviada. Confira o Telegram.")
    except telegram.TelegramError as exc:
        messages.error(request, str(exc))
    return redirect("notifications:settings")
