"""Cartões no MVP-1: cadastro, visão provisória com faturas estimadas, pagamento (F-040, F-041)."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.services import active_accounts
from apps.ledger.errors import LedgerError
from apps.money import Money
from apps.ui.forms import DateInput, IdempotentForm, MoneyField, StyledForm

from . import cycle, services
from .models import Card, OpeningKind


class CardForm(StyledForm):
    name = forms.CharField(label="Nome", max_length=60)
    issuer = forms.CharField(label="Emissor", max_length=60, required=False)
    credit_limit = MoneyField(label="Limite total")
    closing_day = forms.IntegerField(label="Dia de fechamento", min_value=1, max_value=31)
    due_day = forms.IntegerField(label="Dia de vencimento", min_value=1, max_value=31)
    default_payment_account = forms.ModelChoiceField(
        label="Conta que paga a fatura", queryset=active_accounts(), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_payment_account"].queryset = active_accounts()


class PayForm(IdempotentForm):
    account = forms.ModelChoiceField(
        label="Pagar com", queryset=active_accounts(), empty_label=None
    )
    amount = MoneyField(label="Valor pago")
    on = forms.DateField(label="Data", widget=DateInput())

    def __init__(self, *args, card=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts().exclude(asset_class="benefit")
        self.initial.setdefault("on", timezone.localdate())
        if card and card.default_payment_account_id:
            self.initial.setdefault("account", card.default_payment_account_id)


class OpeningItemForm(StyledForm):
    kind = forms.ChoiceField(label="Tipo de item", choices=OpeningKind.choices)
    description = forms.CharField(label="Descrição", max_length=120, required=False)
    amount = MoneyField(label="Valor (faturas)", required=False)
    due_date = forms.DateField(
        label="Vencimento da fatura / da 1ª parcela restante", widget=DateInput(), required=False
    )
    purchase_date = forms.DateField(
        label="Data original da compra", widget=DateInput(), required=False
    )
    total = MoneyField(label="Total da compra (parcelada)", required=False)
    installments = forms.IntegerField(
        label="Número de parcelas", min_value=2, max_value=48, required=False
    )
    billed = forms.IntegerField(
        label="Parcelas já faturadas", min_value=0, max_value=47, required=False
    )
    person = forms.CharField(label="É de outra pessoa? Nome", max_length=60, required=False)


@require_http_methods(["GET"])
def list_view(request):
    today = timezone.localdate()
    rows = []
    for card in services.active_cards():
        estimates = services.estimate(card, today)
        upcoming = next((e for e in estimates if e.due_date >= today), None)
        rows.append(
            {
                "card": card,
                "owed": services.liability(card),
                "available": services.available_limit(card),
                "next": upcoming,
            }
        )
    return render(request, "cards/list.html", {"rows": rows})


@require_http_methods(["GET", "POST"])
def create(request):
    form = CardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            card = services.create_card(**form.cleaned_data)
            messages.success(request, f"Cartão “{card.name}” criado.")
            return redirect("cards:detail", pk=card.pk)
        except LedgerError as exc:
            form.add_error(None, str(exc))
    return render(request, "cards/form.html", {"form": form})


@require_http_methods(["GET"])
def detail(request, pk):
    card = get_object_or_404(Card, pk=pk)
    today = timezone.localdate()
    next_cycle = cycle.closing_date(today, card.closing_day, card.closing_day_goes_next)
    return render(
        request,
        "cards/detail.html",
        {
            "card": card,
            "owed": services.liability(card),
            "available": services.available_limit(card),
            "limit": Money(card.credit_limit_cents),
            "estimates": services.estimate(card, today),
            "purchases": services.recent_purchases(card),
            "payments": [
                (t, Money(sum(p.amount_cents for p in t.postings.all() if p.amount_cents > 0)))
                for t in services.payments(card).prefetch_related("postings")[:10]
            ],
            "pay_form": PayForm(card=card),
            "item_form": OpeningItemForm(),
            "next_closing": next_cycle,
            "next_due": cycle.due_date_for(next_cycle, card.closing_day, card.due_day),
        },
    )


@require_POST
def pay(request, pk):
    card = get_object_or_404(Card, pk=pk)
    form = PayForm(request.POST, card=card)
    if form.is_valid():
        try:
            services.pay(
                card=card,
                account=form.cleaned_data["account"],
                amount=form.cleaned_data["amount"],
                on=form.cleaned_data["on"],
                idempotency_key=form.cleaned_data["idempotency_key"],
            )
            messages.success(request, f"Pagamento de {form.cleaned_data['amount']} registrado.")
        except LedgerError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Confira os dados do pagamento.")
    return redirect("cards:detail", pk=pk)


@require_POST
def add_opening_item(request, pk):
    card = get_object_or_404(Card, pk=pk)
    form = OpeningItemForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            from apps.persons import services as persons

            person = persons.get_or_create(d["person"]) if d.get("person") else None
            services.record_opening_item(
                card=card,
                kind=d["kind"],
                description=d.get("description") or "",
                amount=d.get("amount"),
                due_date=d.get("due_date"),
                purchase_date=d.get("purchase_date"),
                total=d.get("total"),
                installments=d.get("installments") or 1,
                billed=d.get("billed") or 0,
                person=person,
            )
            messages.success(request, "Item de abertura registrado.")
        except LedgerError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Confira os dados do item.")
    return redirect("cards:detail", pk=pk)
