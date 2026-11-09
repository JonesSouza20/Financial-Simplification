"""Dívida e consórcio provisórios (F-060; RN-117, RN-118)."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.services import active_accounts
from apps.ledger.errors import LedgerError
from apps.money import Money
from apps.ui.forms import DateInput, IdempotentForm, MoneyField, StyledForm

from . import services
from .models import Debt, DebtKind


class LoanForm(StyledForm):
    creditor = forms.CharField(label="Credor", max_length=60)
    description = forms.CharField(label="Descrição", max_length=120, required=False)
    balance = MoneyField(label="Saldo devedor em 01/11/2026")
    monthly_rate_percent = forms.CharField(
        label="Taxa de juros (% ao mês)", max_length=12, required=False
    )
    remaining_installments = forms.IntegerField(
        label="Parcelas restantes", min_value=1, max_value=360, required=False
    )
    contract_installment = MoneyField(label="Valor da parcela do contrato", required=False)
    due_day = forms.IntegerField(label="Dia de vencimento", min_value=1, max_value=31)


class ConsortiumForm(StyledForm):
    description = forms.CharField(label="Descrição", max_length=120, initial="Consórcio do veículo")
    installment = MoneyField(label="Valor da parcela")
    remaining_installments = forms.IntegerField(
        label="Parcelas restantes", min_value=1, max_value=360
    )
    due_day = forms.IntegerField(label="Dia de vencimento", min_value=1, max_value=31)


class PayLoanForm(IdempotentForm):
    account = forms.ModelChoiceField(label="Pago com", queryset=active_accounts(), empty_label=None)
    principal = MoneyField(label="Principal (amortização)")
    interest = MoneyField(label="Juros", required=False)
    charges = MoneyField(label="Encargos (seguro, tarifas)", required=False)
    on = forms.DateField(label="Data", widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts().exclude(asset_class="benefit")
        self.initial.setdefault("on", timezone.localdate())


class PayConsortiumForm(IdempotentForm):
    account = forms.ModelChoiceField(label="Pago com", queryset=active_accounts(), empty_label=None)
    amount = MoneyField(label="Valor pago")
    on = forms.DateField(label="Data", widget=DateInput())

    def __init__(self, *args, debt=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts().exclude(asset_class="benefit")
        self.initial.setdefault("on", timezone.localdate())
        if debt and debt.contract_installment_cents:
            self.initial.setdefault(
                "amount", Money(debt.contract_installment_cents).format_brl().replace("R$ ", "")
            )


@require_http_methods(["GET"])
def list_view(request):
    rows = [(d, services.balance(d)) for d in services.active()]
    total = Money.sum([b for d, b in rows])
    return render(request, "debts/list.html", {"rows": rows, "total": total})


@require_http_methods(["GET", "POST"])
def create_loan(request):
    form = LoanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            debt = services.create_loan(**form.cleaned_data)
            messages.success(request, "Dívida cadastrada com o saldo de abertura.")
            return redirect("debts:detail", pk=debt.pk)
        except LedgerError as exc:
            form.add_error(None, str(exc))
    return render(request, "debts/form.html", {"form": form, "title": "Nova dívida"})


@require_http_methods(["GET", "POST"])
def create_consortium(request):
    form = ConsortiumForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            debt = services.create_consortium(**form.cleaned_data)
            messages.success(request, "Consórcio cadastrado.")
            return redirect("debts:detail", pk=debt.pk)
        except LedgerError as exc:
            form.add_error(None, str(exc))
    return render(request, "debts/form.html", {"form": form, "title": "Novo consórcio"})


@require_http_methods(["GET"])
def detail(request, pk):
    debt = get_object_or_404(Debt, pk=pk)
    form = PayLoanForm() if debt.kind == DebtKind.LOAN else PayConsortiumForm(debt=debt)
    return render(
        request,
        "debts/detail.html",
        {
            "debt": debt,
            "balance": services.balance(debt),
            "history": services.history(debt)[:50],
            "form": form,
        },
    )


@require_POST
def pay(request, pk):
    debt = get_object_or_404(Debt, pk=pk)
    try:
        if debt.kind == DebtKind.LOAN:
            form = PayLoanForm(request.POST)
            if form.is_valid():
                d = form.cleaned_data
                services.pay_loan(
                    debt=debt,
                    account=d["account"],
                    principal=d["principal"],
                    interest=d["interest"] or Money(0),
                    charges=d["charges"] or Money(0),
                    on=d["on"],
                    idempotency_key=d["idempotency_key"],
                )
        else:
            form = PayConsortiumForm(request.POST, debt=debt)
            if form.is_valid():
                d = form.cleaned_data
                from apps.payables import services as payables

                # Com parcela prevista, liquida o compromisso em vez de criar um segundo T19.
                planned = payables.oldest_open_consortium(debt)
                if planned is not None:
                    payables.pay(
                        planned,
                        amount=d["amount"],
                        account=d["account"],
                        on=d["on"],
                        idempotency_key=d["idempotency_key"],
                    )
                else:
                    services.pay_consortium(
                        debt=debt,
                        account=d["account"],
                        amount=d["amount"],
                        on=d["on"],
                        idempotency_key=d["idempotency_key"],
                    )
        if form.is_valid():
            messages.success(request, "Parcela registrada.")
        else:
            messages.error(request, "Confira os valores da parcela.")
    except LedgerError as exc:
        messages.error(request, str(exc))
    return redirect("debts:detail", pk=pk)
