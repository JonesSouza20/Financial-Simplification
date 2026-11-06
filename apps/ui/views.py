"""Início, aparência e arquivos do PWA."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.http import require_GET

from apps.accounts import services as accounts
from apps.entries import services as entries
from apps.money import Money


@require_GET
def home(request):
    rows = [(a, accounts.balance(a)) for a in accounts.active_accounts()]
    recent = [entries.describe(t) for t in entries.movements()[:5]]
    return render(
        request,
        "ui/home.html",
        {
            "rows": rows,
            "bank": Money.sum([b for a, b in rows if a.asset_class in ("free", "reserve")]),
            "free": Money.sum([b for a, b in rows if a.asset_class == "free"]),
            "reserve": Money.sum([b for a, b in rows if a.asset_class == "reserve"]),
            "benefit": Money.sum([b for a, b in rows if a.asset_class == "benefit"]),
            "recent": recent,
        },
    )


@require_GET
def appearance(request):
    return render(request, "ui/appearance.html")


@login_not_required
@require_GET
def manifest(request):
    return render(
        request,
        "ui/manifest.webmanifest",
        {"icon": static("img/icon.svg")},
        content_type="application/manifest+json",
    )


@login_not_required
@require_GET
def service_worker(request):
    # Mínimo para instalar como aplicativo (ADR-015). Não guarda dados financeiros em cache.
    body = (settings.BASE_DIR / "static" / "js" / "sw.js").read_text(encoding="utf-8")
    response = HttpResponse(body, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response
