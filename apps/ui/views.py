"""Início, aparência e arquivos do PWA."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts import services as accounts
from apps.money import Money


def _totals():
    """Saldos e posições derivados do Ledger (RN-141, RN-142, RN-147, RN-148)."""
    from apps.cards import services as cards
    from apps.debts import services as debts
    from apps.receivables import services as receivables

    rows = [(a, accounts.balance(a)) for a in accounts.active_accounts()]
    card_rows = [(c, cards.liability(c)) for c in cards.active_cards()]
    debt_rows = [(d, debts.balance(d)) for d in debts.active() if d.kind == "loan"]
    people = [
        (r.person, r.open) for r in receivables.summaries(timezone.localdate()) if r.open.cents
    ]
    by_class = {
        k: Money.sum([b for a, b in rows if a.asset_class == k])
        for k in ("free", "reserve", "benefit")
    }
    return {
        "rows": rows,
        "card_rows": card_rows,
        "debt_rows": debt_rows,
        "people": people,
        "bank": by_class["free"] + by_class["reserve"],
        "free": by_class["free"],
        "reserve": by_class["reserve"],
        "benefit": by_class["benefit"],
        "cards_total": Money.sum([b for _, b in card_rows]),
        "debts_total": Money.sum([b for _, b in debt_rows]),
        "receivable_total": Money.sum([b for _, b in people]),
    }


@require_GET
def home(request):
    from apps.ledger import services as ledger
    from apps.payables import presentation

    from . import models as prefs

    context = presentation.home(ledger.today())
    context["opening_done"] = prefs.get("opening_done", False)
    return render(request, "ui/home.html", context)


ORIGINS = {
    # slug: (título, fórmula, chaves de linhas, filtro por classe)
    "bancario": (
        "Saldo bancário",
        "Soma dos saldos das contas livres e de reserva (RN-141).",
        "rows",
        ("free", "reserve"),
    ),
    "livre": ("Contas livres", "Soma dos saldos das contas de uso geral.", "rows", ("free",)),
    "guardado": ("Total guardado", "Soma das contas de reserva (RN-147).", "rows", ("reserve",)),
    "beneficios": (
        "Saldo de benefícios",
        "Soma das carteiras de VR/VA (RN-142). Não entra em nenhum outro saldo.",
        "rows",
        ("benefit",),
    ),
    "cartoes": (
        "Saldo devedor dos cartões",
        "Compras e itens de abertura menos pagamentos e "
        "estornos, por cartão. Inclui parcelas futuras.",
        "card_rows",
        None,
    ),
    "dividas": (
        "Saldo devedor das dívidas",
        "Saldo de abertura menos o principal das parcelas pagas, por dívida.",
        "debt_rows",
        None,
    ),
    "a-receber": (
        "Valores a receber",
        "O que cada pessoa ainda deve; recebimentos abatem o mais antigo primeiro. Não é receita.",
        "people",
        None,
    ),
}


@require_GET
def origin(request, slug):
    """De onde vem este número (F-071; RF-LED-12)."""
    from django.http import Http404

    if slug not in ORIGINS:
        raise Http404
    title, formula, key, classes = ORIGINS[slug]
    totals = _totals()
    items = totals[key]
    if classes:
        items = [(a, b) for a, b in items if a.asset_class in classes]
    links = {
        "rows": "accounts:detail",
        "card_rows": "cards:detail",
        "debt_rows": "debts:detail",
        "people": "receivables:detail",
    }
    return render(
        request,
        "ui/origin.html",
        {
            "title": title,
            "formula": formula,
            "items": items,
            "link": links[key],
            "total": Money.sum([b for _, b in items]),
        },
    )


@require_GET
def more(request):
    """Menu completo no celular (ui-ux-specification.md §8.3)."""
    return render(request, "ui/more.html")


@require_GET
def settings_hub(request):
    """Ajustes: o que é usado raramente sai da navegação principal (design-study.md §10)."""
    return render(request, "ui/settings.html")


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
