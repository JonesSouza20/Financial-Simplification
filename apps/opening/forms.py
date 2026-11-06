"""Formulários do assistente de abertura. Cada um vira um item do rascunho (centavos e ISO)."""

from django import forms

from apps.accounts.models import DEFAULT_CLASS, AccountType, AssetClassChoice
from apps.cards.models import OpeningKind
from apps.ui.forms import DateInput, MoneyField, StyledForm


def _cents(value):
    return value.cents if value is not None else None


def _iso(value):
    return value.isoformat() if value else None


class AccountDraftForm(StyledForm):
    name = forms.CharField(label="Nome da conta", max_length=60)
    account_type = forms.ChoiceField(label="Tipo", choices=AccountType.choices)
    asset_class = forms.ChoiceField(
        label="Classe",
        choices=[("", "Automática pelo tipo")] + list(AssetClassChoice.choices),
        required=False,
    )
    institution = forms.CharField(label="Instituição", max_length=60, required=False)
    balance = MoneyField(label="Saldo em 01/11/2026", allow_negative=True)

    def item(self):
        d = self.cleaned_data
        return {
            "name": d["name"],
            "account_type": d["account_type"],
            "asset_class": d["asset_class"] or DEFAULT_CLASS[d["account_type"]],
            "institution": d["institution"],
            "balance": d["balance"].cents,
        }


class CardDraftForm(StyledForm):
    name = forms.CharField(label="Nome do cartão", max_length=60)
    issuer = forms.CharField(label="Emissor", max_length=60, required=False)
    credit_limit = MoneyField(label="Limite total")
    closing_day = forms.IntegerField(label="Dia de fechamento", min_value=1, max_value=31)
    due_day = forms.IntegerField(label="Dia de vencimento", min_value=1, max_value=31)

    def clean(self):
        d = super().clean()
        if d.get("closing_day") and d.get("closing_day") == d.get("due_day"):
            raise forms.ValidationError("Fechamento e vencimento não podem ser no mesmo dia.")
        if d.get("credit_limit") is not None and not d["credit_limit"].is_positive:
            self.add_error("credit_limit", "O limite deve ser maior que zero.")
        return d

    def item(self):
        d = self.cleaned_data
        return {
            "name": d["name"],
            "issuer": d["issuer"],
            "limit": d["credit_limit"].cents,
            "closing_day": d["closing_day"],
            "due_day": d["due_day"],
        }


class ItemDraftForm(StyledForm):
    card = forms.TypedChoiceField(label="Cartão", coerce=int, choices=[])
    kind = forms.ChoiceField(label="Tipo de item", choices=OpeningKind.choices)
    description = forms.CharField(label="Descrição", max_length=120, required=False)
    amount = MoneyField(label="Valor (fatura fechada ou aberta)", required=False)
    due_date = forms.DateField(
        label="Vencimento da fatura ou da 1ª parcela restante", widget=DateInput(), required=False
    )
    purchase_date = forms.DateField(
        label="Data original da compra", widget=DateInput(), required=False
    )
    total = MoneyField(label="Total da compra parcelada", required=False)
    installments = forms.IntegerField(
        label="Número de parcelas", min_value=2, max_value=48, required=False
    )
    billed = forms.IntegerField(
        label="Parcelas já faturadas", min_value=0, max_value=47, required=False
    )
    person = forms.CharField(label="É de outra pessoa? Nome", max_length=60, required=False)

    def __init__(self, *args, cards=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["card"].choices = [(i, c["name"]) for i, c in enumerate(cards)]

    def clean(self):
        d = super().clean()
        if d.get("kind") == OpeningKind.REMAINING:
            if not d.get("total") or not d.get("installments"):
                raise forms.ValidationError(
                    "Parcelas restantes: informe o total e o número de parcelas."
                )
            if (d.get("billed") or 0) >= d["installments"]:
                self.add_error("billed", "Parcelas já faturadas devem ser menos que o total.")
        elif d.get("kind") and (d.get("amount") is None or not d["amount"].is_positive):
            self.add_error("amount", "Informe o valor da fatura.")
        return d

    def item(self):
        d = self.cleaned_data
        return {
            "card": d["card"],
            "kind": d["kind"],
            "description": d["description"],
            "amount": _cents(d.get("amount")),
            "due_date": _iso(d.get("due_date")),
            "purchase_date": _iso(d.get("purchase_date")),
            "total": _cents(d.get("total")),
            "installments": d.get("installments") or 1,
            "billed": d.get("billed") or 0,
            "person": (d.get("person") or "").strip(),
        }


class DebtDraftForm(StyledForm):
    kind = forms.ChoiceField(
        label="Tipo", choices=[("loan", "Empréstimo ou financiamento"), ("consortium", "Consórcio")]
    )
    creditor = forms.CharField(label="Credor", max_length=60, required=False)
    description = forms.CharField(label="Descrição", max_length=120, required=False)
    balance = MoneyField(label="Saldo devedor (empréstimo)", required=False)
    rate = forms.CharField(label="Taxa (% ao mês)", max_length=12, required=False)
    remaining = forms.IntegerField(
        label="Parcelas restantes", min_value=1, max_value=360, required=False
    )
    installment = MoneyField(label="Valor da parcela", required=False)
    due_day = forms.IntegerField(label="Dia de vencimento", min_value=1, max_value=31)

    def clean(self):
        d = super().clean()
        if d.get("kind") == "loan":
            if not d.get("creditor"):
                self.add_error("creditor", "Informe o credor.")
            if not d.get("balance") or not d["balance"].is_positive:
                self.add_error("balance", "Informe o saldo devedor.")
        elif d.get("kind") == "consortium" and not (d.get("installment") and d.get("remaining")):
            raise forms.ValidationError("Consórcio: informe a parcela e as parcelas restantes.")
        return d

    def item(self):
        d = self.cleaned_data
        return {
            "kind": d["kind"],
            "creditor": d["creditor"],
            "description": d["description"],
            "balance": _cents(d.get("balance")),
            "rate": d.get("rate") or "",
            "remaining": d.get("remaining"),
            "installment": _cents(d.get("installment")),
            "due_day": d["due_day"],
        }


class ReceivableDraftForm(StyledForm):
    person = forms.CharField(label="Pessoa", max_length=60)
    description = forms.CharField(label="Descrição", max_length=120, required=False)
    amount = MoneyField(label="Quanto deve")
    due_date = forms.DateField(label="Previsão de recebimento", widget=DateInput())

    def item(self):
        d = self.cleaned_data
        return {
            "person": d["person"].strip(),
            "description": d["description"],
            "amount": d["amount"].cents,
            "due_date": d["due_date"].isoformat(),
        }
