"""Lançar, listar, detalhar, corrigir, estornar, anotar e desfazer (F-010 a F-014)."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.reconciliation import reconciled_after
from apps.ledger import services as ledger
from apps.ledger.errors import LedgerError
from apps.ledger.models import CARD_PURCHASE_TYPES, AuditLog, LedgerTransaction
from apps.security.views import _safe_next
from apps.ui.forms import MoneyField

from . import services
from .forms import EntryForm, FilterForm, NoteForm, ReasonForm
from .services import EXPENSE, INCOME, TRANSFER


def _save(request, form, *, template, context=None, correcting=None):
    """Valida, avisa duplicidade e período conciliado, e grava. Devolve None para re-renderizar."""
    try:
        entry = form.entry()
        data = form.cleaned_data
        if correcting is None and not data.get("confirm_duplicate"):
            duplicate = services.possible_duplicate(entry)
            if duplicate is not None:
                form.duplicate = duplicate
                return None
        account = getattr(entry, "account", None)
        if account is not None and not data.get("confirm_reconciled"):
            marker = reconciled_after(account, entry.on).first()
            if marker is not None:
                form.reconciled = marker
                return None
        if correcting is not None:
            return services.correct(
                correcting,
                entry,
                reason="Corrigido pelo usuário",
                idempotency_key=data["idempotency_key"],
            )
        return services.record(entry, idempotency_key=data["idempotency_key"])
    except LedgerError as exc:
        form.add_error(None, str(exc))
        return None


@require_http_methods(["GET", "POST"])
def quick(request):
    """Lançamento rápido (F-010): salva e volta para o próximo."""
    kind = request.GET.get("tipo", EXPENSE)
    form = EntryForm(request.POST or None, initial={"kind": kind})
    if request.method == "POST" and form.is_valid():
        txn = _save(request, form, template="entries/quick.html")
        if txn is not None:
            view = services.describe(txn)
            request.session["undo_txn"] = txn.pk
            messages.success(
                request,
                f"{view.label} de {view.amount} em {view.account} salvo.",
                extra_tags="undo",
            )
            return redirect("entries:quick")
    return render(
        request, "entries/quick.html", {"form": form, "kinds": (EXPENSE, INCOME, TRANSFER)}
    )


@require_http_methods(["GET", "POST"])
def new(request):
    """Lançamento completo (F-011), com competência e observação."""
    form = EntryForm(request.POST or None, initial={"kind": request.GET.get("tipo", EXPENSE)})
    if request.method == "POST" and form.is_valid():
        txn = _save(request, form, template="entries/form.html")
        if txn is not None:
            messages.success(request, "Lançamento salvo.")
            return redirect("entries:detail", pk=txn.pk)
    return render(request, "entries/form.html", {"form": form, "title": "Novo lançamento"})


@require_http_methods(["GET"])
def list_view(request):
    form = FilterForm(request.GET or None)
    filters = form.cleaned_data if form.is_valid() else {}
    qs = services.movements(**{k: v for k, v in filters.items() if v not in (None, "")})
    page = Paginator(qs, 50).get_page(request.GET.get("pagina"))
    rows = [services.describe(t) for t in page.object_list]
    total = sum((r.signed.cents for r in rows), 0)
    template = "entries/_rows.html" if request.headers.get("HX-Request") else "entries/list.html"
    return render(
        request, template, {"form": form, "page": page, "rows": rows, "page_total": total}
    )


@require_http_methods(["GET"])
def detail(request, pk):
    txn = get_object_or_404(LedgerTransaction, pk=pk)
    links = list(txn.links_in.select_related("from_transaction")) + list(
        txn.links_out.select_related("to_transaction")
    )
    audit_rows = AuditLog.objects.filter(entity_type="ledger_transaction", entity_id=txn.pk)
    return render(
        request,
        "entries/detail.html",
        {
            "view": services.describe(txn),
            "links_in": txn.links_in.select_related("from_transaction"),
            "links_out": txn.links_out.select_related("to_transaction"),
            "has_links": bool(links),
            "notes": txn.notes.order_by("created_at"),
            "audit_rows": audit_rows.order_by("at"),
            "reason_form": ReasonForm(),
            "note_form": NoteForm(),
            "is_card": txn.type in CARD_PURCHASE_TYPES,
        },
    )


@require_http_methods(["GET", "POST"])
def correct(request, pk):
    txn = get_object_or_404(LedgerTransaction, pk=pk)
    view = services.describe(txn)
    if not view.editable:
        messages.error(request, "Este lançamento não pode ser corrigido.")
        return redirect("entries:detail", pk=pk)
    initial = _initial_from(txn, view)
    form = EntryForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        new_txn = _save(request, form, template="entries/form.html", correcting=txn)
        if new_txn is not None:
            messages.success(request, "Lançamento corrigido. O original foi estornado.")
            return redirect("entries:detail", pk=new_txn.pk)
    return render(
        request,
        "entries/form.html",
        {"form": form, "title": "Corrigir lançamento", "correcting": txn},
    )


def _initial_from(txn, view):
    from apps.accounts.models import FinancialAccount
    from apps.categories.models import Category

    initial = {
        "kind": view.kind,
        "amount": view.amount.format_brl().replace("R$ ", ""),
        "on": txn.operation_date,
        "competence": txn.competence_date,
        "description": txn.description,
    }
    for p in txn.postings.select_related("account"):
        if p.account.owner_type == "financial_account":
            acc = FinancialAccount.objects.get(pk=p.account.owner_id)
            if view.kind == TRANSFER and p.amount_cents > 0:
                initial["destination"] = acc
            else:
                initial["account"] = acc
        elif p.account.owner_type == "category":
            cat = Category.objects.get(pk=p.account.owner_id)
            initial["expense_category" if view.kind == EXPENSE else "income_category"] = cat
    return initial


@require_POST
def reverse(request, pk):
    """Estornar (F-014). Compra no cartão: lançamento errado (técnico) ou devolução do lojista
    (comercial), total ou parcial (RN-082 a RN-084, RN-121)."""
    txn = get_object_or_404(LedgerTransaction, pk=pk)
    form = ReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe o motivo do estorno.")
        return redirect("entries:detail", pk=pk)
    reason = form.cleaned_data["reason"]
    mode = request.POST.get("mode", "technical")
    try:
        partial = None
        if txn.type in CARD_PURCHASE_TYPES and mode == "commercial" and request.POST.get("amount"):
            try:
                partial = MoneyField().clean(request.POST["amount"])
            except Exception:  # noqa: BLE001 - mensagem amigável abaixo
                raise LedgerError("Valor do estorno inválido. Use o formato 1.234,56.") from None
        if partial is not None:
            reversal = ledger.reverse_partially(txn, amount=partial, reason=reason)
        else:
            reversal = ledger.reverse(txn, reason=reason, mode=mode)
        messages.success(request, "Lançamento estornado. Nada foi apagado.")
        return redirect("entries:detail", pk=reversal.pk)
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("entries:detail", pk=pk)


@require_POST
def note(request, pk):
    txn = get_object_or_404(LedgerTransaction, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        ledger.add_note(txn, form.cleaned_data["text"])
        messages.success(request, "Nota acrescentada.")
    return redirect("entries:detail", pk=pk)


@require_POST
def undo(request):
    pk = request.session.pop("undo_txn", None)
    txn = LedgerTransaction.objects.filter(pk=pk).first() if pk else None
    if txn is None:
        messages.error(request, "Nada para desfazer.")
    else:
        try:
            services.undo(txn)
            messages.success(request, "Lançamento desfeito.")
        except LedgerError as exc:
            messages.error(request, str(exc))
    return redirect(_safe_next(request, "entries:quick"))
