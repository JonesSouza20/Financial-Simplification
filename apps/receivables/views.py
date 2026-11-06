"""Pessoas e valores a receber no MVP-1 (F-050 a F-052, versão simples)."""

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.services import active_accounts
from apps.ledger.errors import LedgerError
from apps.persons import services as persons
from apps.persons.models import Person
from apps.ui.forms import DateInput, IdempotentForm, MoneyField

from . import services
from .models import ReceivableAllocation


class LendForm(IdempotentForm):
    person = forms.CharField(
        label="Pessoa", max_length=60, widget=forms.TextInput(attrs={"list": "people"})
    )
    account = forms.ModelChoiceField(
        label="Saiu da conta", queryset=active_accounts(), empty_label=None
    )
    amount = MoneyField(label="Valor emprestado")
    on = forms.DateField(label="Data", widget=DateInput())
    due_date = forms.DateField(label="Previsão de recebimento", widget=DateInput())
    description = forms.CharField(label="Descrição", max_length=120, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts().exclude(asset_class="benefit")
        self.initial.setdefault("on", timezone.localdate())


class ReceiveForm(IdempotentForm):
    account = forms.ModelChoiceField(
        label="Entrou na conta", queryset=active_accounts(), empty_label=None
    )
    amount = MoneyField(label="Valor recebido")
    on = forms.DateField(label="Data", widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts().exclude(asset_class="benefit")
        self.initial.setdefault("on", timezone.localdate())


@require_http_methods(["GET", "POST"])
def list_view(request):
    form = LendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            person = persons.get_or_create(d["person"])
            services.lend(
                person=person,
                account=d["account"],
                amount=d["amount"],
                on=d["on"],
                due_date=d["due_date"],
                description=d["description"] or "",
                idempotency_key=d["idempotency_key"],
            )
            messages.success(request, f"Empréstimo para {person.name} registrado.")
            return redirect("receivables:detail", pk=person.pk)
        except LedgerError as exc:
            form.add_error(None, str(exc))
    rows = services.summaries(timezone.localdate())
    return render(
        request,
        "receivables/list.html",
        {
            "rows": rows,
            "form": form,
            "people": [r.person.name for r in rows],
        },
    )


@require_http_methods(["GET"])
def detail(request, pk):
    person = get_object_or_404(Person, pk=pk)
    today = timezone.localdate()
    return render(
        request,
        "receivables/detail.html",
        {
            "person": person,
            "pending": services.open_installments(person),
            "total": services.open_total(person),
            "today": today,
            "history": ReceivableAllocation.objects.filter(installment__receivable__person=person)
            .select_related("transaction", "installment__receivable")
            .order_by("-id")[:50],
            "receivables": person.receivables.select_related("origin_transaction").order_by("-id"),
            "form": ReceiveForm(),
        },
    )


@require_POST
def receive(request, pk):
    person = get_object_or_404(Person, pk=pk)
    form = ReceiveForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.receive(
                person=person,
                account=d["account"],
                amount=d["amount"],
                on=d["on"],
                idempotency_key=d["idempotency_key"],
            )
            messages.success(request, f"Recebimento de {d['amount']} registrado. Não é receita.")
        except LedgerError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Confira os dados do recebimento.")
    return redirect("receivables:detail", pk=pk)
