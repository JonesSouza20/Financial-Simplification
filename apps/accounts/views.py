"""Contas financeiras: lista com saldos, cadastro, histórico, arquivamento (F-020)."""

from django import forms
from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.entries.services import account_history
from apps.ledger.errors import LedgerError
from apps.money import Money
from apps.ui.forms import DateInput, MoneyField, StyledForm

from . import reconciliation, services
from .models import DEFAULT_CLASS, AccountType, AssetClassChoice, FinancialAccount


class AccountForm(StyledForm):
    name = forms.CharField(label="Nome", max_length=60)
    account_type = forms.ChoiceField(label="Tipo", choices=AccountType.choices)
    asset_class = forms.ChoiceField(
        label="Classe",
        choices=AssetClassChoice.choices,
        required=False,
        help_text="Livre entra no disponível; reserva fica guardada; benefício é VR/VA.",
    )
    institution = forms.CharField(label="Instituição", max_length=60, required=False)
    opening_balance = MoneyField(label="Saldo inicial", allow_negative=True, required=False)
    opening_date = forms.DateField(label="Data do saldo inicial", widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault(
            "opening_date", max(settings.FINANCAS_START_DATE, timezone.localdate())
        )


@require_http_methods(["GET"])
def list_view(request):
    accounts = list(services.active_accounts())
    rows = [(a, services.balance(a)) for a in accounts]
    totals = {
        "bank": Money.sum([b for a, b in rows if a.asset_class in ("free", "reserve")]),
        "reserve": Money.sum([b for a, b in rows if a.asset_class == "reserve"]),
        "benefit": Money.sum([b for a, b in rows if a.asset_class == "benefit"]),
    }
    return render(request, "accounts/list.html", {"rows": rows, "totals": totals})


@require_http_methods(["GET", "POST"])
def create(request):
    form = AccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            account = services.create_account(
                name=d["name"],
                account_type=d["account_type"],
                asset_class=d["asset_class"] or DEFAULT_CLASS[d["account_type"]],
                institution=d["institution"],
                opening_balance=d["opening_balance"] or Money(0),
                opening_date=d["opening_date"],
            )
            messages.success(request, f"Conta “{account.name}” criada.")
            return redirect("accounts:detail", pk=account.pk)
        except LedgerError as exc:
            form.add_error(None, str(exc))
    return render(request, "accounts/form.html", {"form": form})


@require_http_methods(["GET"])
def detail(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    return render(
        request,
        "accounts/detail.html",
        {
            "account": account,
            "balance": services.balance(account),
            "history": account_history(account)[:200],
            "reconcile_form": ReconcileForm(),
            "reconciliations": account.reconciliations.all()[:10],
        },
    )


class ReconcileForm(StyledForm):
    on = forms.DateField(label="Data do saldo no banco", widget=DateInput())
    informed = MoneyField(label="Saldo que o banco mostra", allow_negative=True)
    adjust = forms.BooleanField(label="Não achei a diferença: registrar ajuste", required=False)
    notes = forms.CharField(label="Motivo do ajuste", max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("on", timezone.localdate())


@require_POST
def reconcile(request, pk):
    """Conciliação de saldo (F-022; RN-130, RN-131)."""
    account = get_object_or_404(FinancialAccount, pk=pk)
    form = ReconcileForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            rec = reconciliation.reconcile(
                account=account,
                on=d["on"],
                informed=d["informed"],
                adjust=d["adjust"],
                notes=d["notes"] or "",
            )
            if rec.difference_cents:
                messages.success(
                    request,
                    f"Ajuste de {Money(rec.difference_cents)} registrado. "
                    "Não é receita nem despesa.",
                )
            else:
                messages.success(request, "Saldo conferido: igual ao do banco.")
        except LedgerError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Confira a data e o saldo informados.")
    return redirect("accounts:detail", pk=pk)


@require_POST
def archive(request, pk):
    account = get_object_or_404(FinancialAccount, pk=pk)
    try:
        services.archive(account)
        messages.success(request, f"Conta “{account.name}” arquivada.")
        return redirect("accounts:list")
    except LedgerError as exc:
        messages.error(request, str(exc))
        return redirect("accounts:detail", pk=pk)
