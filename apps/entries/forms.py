from django import forms
from django.utils import timezone

from apps.accounts.services import active_accounts
from apps.categories.models import Category, CategoryKind
from apps.categories.services import selectable
from apps.ledger.models import TransactionStatus
from apps.ui.forms import DateInput, IdempotentForm, MoneyField, StyledForm

from .services import EXPENSE, INCOME, TRANSFER, EntryInput


class CategoryChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return str(obj)


class EntryForm(IdempotentForm):
    kind = forms.ChoiceField(
        label="Tipo",
        choices=[(EXPENSE, "Gasto"), (INCOME, "Recebimento"), (TRANSFER, "Transferência")],
        widget=forms.RadioSelect,
        initial=EXPENSE,
    )
    amount = MoneyField()
    account = forms.ModelChoiceField(label="Conta", queryset=active_accounts(), empty_label=None)
    destination = forms.ModelChoiceField(
        label="Para a conta", queryset=active_accounts(), required=False
    )
    expense_category = CategoryChoice(
        label="Categoria",
        queryset=Category.objects.none(),
        required=False,
        empty_label="Escolha a categoria",
    )
    income_category = CategoryChoice(
        label="Categoria",
        queryset=Category.objects.none(),
        required=False,
        empty_label="Escolha a categoria",
    )
    on = forms.DateField(label="Data", widget=DateInput())
    competence = forms.DateField(
        label="Competência (mês a que pertence)",
        widget=DateInput(),
        required=False,
        help_text="Deixe em branco para usar a data do lançamento.",
    )
    description = forms.CharField(label="Descrição", max_length=200, required=False)
    confirm_duplicate = forms.BooleanField(label="Salvar mesmo assim", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts()
        self.fields["destination"].queryset = active_accounts()
        self.fields["expense_category"].queryset = selectable(CategoryKind.EXPENSE)
        self.fields["income_category"].queryset = Category.objects.filter(
            kind=CategoryKind.INCOME, archived_at__isnull=True
        ).exclude(system_key="reserve_yield")
        self.initial.setdefault("on", timezone.localdate())

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        if kind == EXPENSE and not data.get("expense_category"):
            self.add_error("expense_category", "Escolha uma categoria.")
        if kind == INCOME and not data.get("income_category"):
            self.add_error("income_category", "Escolha uma categoria.")
        if kind == TRANSFER and not data.get("destination"):
            self.add_error("destination", "Escolha a conta de destino.")
        return data

    def entry(self) -> EntryInput:
        d = self.cleaned_data
        category = d.get("expense_category") if d["kind"] == EXPENSE else d.get("income_category")
        return EntryInput(
            kind=d["kind"],
            amount=d["amount"],
            account=d["account"],
            on=d["on"],
            description=d.get("description") or "",
            category=category if d["kind"] != TRANSFER else None,
            destination=d.get("destination") if d["kind"] == TRANSFER else None,
            competence=d.get("competence"),
        )


class ReasonForm(StyledForm):
    reason = forms.CharField(label="Motivo", max_length=200)


class NoteForm(StyledForm):
    text = forms.CharField(label="Nota", max_length=500, widget=forms.Textarea(attrs={"rows": 2}))


class FilterForm(StyledForm):
    start = forms.DateField(label="De", required=False, widget=DateInput())
    end = forms.DateField(label="Até", required=False, widget=DateInput())
    account = forms.ModelChoiceField(label="Conta", queryset=active_accounts(), required=False)
    category = CategoryChoice(label="Categoria", queryset=Category.objects.none(), required=False)
    status = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=[("", "Todos")]
        + [(s.value, s.label) for s in TransactionStatus if s != TransactionStatus.DRAFT],
    )
    text = forms.CharField(label="Busca", required=False)
    by_competence = forms.BooleanField(label="Por competência", required=False)
    show_all = forms.BooleanField(label="Mostrar estornos e cancelados", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts()
        self.fields["category"].queryset = Category.objects.filter(
            archived_at__isnull=True
        ).select_related("parent")
