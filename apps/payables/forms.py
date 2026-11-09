"""Formulários de contas a pagar, receitas previstas e recorrências (F-030 a F-033, F-036)."""

from django import forms

from apps.accounts.services import active_accounts
from apps.categories.models import Category, CategoryKind
from apps.categories.services import selectable
from apps.ledger import services as ledger
from apps.ui.forms import DateInput, IdempotentForm, MoneyField, StyledForm

from .models import DayRule, ExcessKind, Frequency, PaymentMethod, ValueType

VALUE_TYPES = [(ValueType.FIXED, "Valor fixo"), (ValueType.VARIABLE, "Valor varia (estimativa)")]


class Sectioned:
    """Separa os campos do dia a dia dos que ficam em "Mais opções"."""

    advanced: tuple[str, ...] = ()

    @property
    def basic_fields(self):
        return [f for f in self.visible_fields() if f.name not in self.advanced]

    @property
    def advanced_fields(self):
        return [f for f in self.visible_fields() if f.name in self.advanced]

    @property
    def advanced_open(self):
        return any(f.errors for f in self.advanced_fields)


class BillForm(Sectioned, IdempotentForm):
    advanced = ("value_type", "installments", "payment_method", "reference_month", "anticipates")

    description = forms.CharField(label="Nome", max_length=120)
    amount = MoneyField(label="Valor")
    due_date = forms.DateField(label="Vencimento", widget=DateInput())
    category = forms.ModelChoiceField(
        label="Categoria", queryset=Category.objects.none(), empty_label="Escolha a categoria"
    )
    account = forms.ModelChoiceField(
        label="Conta prevista", queryset=active_accounts(), empty_label=None
    )
    value_type = forms.ChoiceField(label="Tipo de valor", choices=VALUE_TYPES)
    installments = forms.IntegerField(
        label="Parcelas",
        min_value=1,
        max_value=120,
        initial=1,
        help_text="Com mais de uma, o valor acima é o total e o tipo é sempre fixo.",
    )
    payment_method = forms.ChoiceField(
        label="Forma de pagamento",
        choices=[("", "Não informar"), *PaymentMethod.choices],
        required=False,
    )
    reference_month = forms.CharField(
        label="Competência (AAAA-MM)",
        max_length=7,
        required=False,
        help_text="Deixe em branco para usar o mês do vencimento.",
    )
    anticipates = forms.BooleanField(label="Antecipa se cair em dia não útil", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts()
        self.fields["category"].queryset = selectable(CategoryKind.EXPENSE)


class IncomeForm(Sectioned, IdempotentForm):
    description = forms.CharField(label="Nome", max_length=120)
    amount = MoneyField(label="Valor")
    due_date = forms.DateField(label="Data prevista", widget=DateInput())
    category = forms.ModelChoiceField(
        label="Categoria", queryset=Category.objects.none(), empty_label="Escolha a categoria"
    )
    account = forms.ModelChoiceField(label="Entra em", queryset=active_accounts(), empty_label=None)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts()
        self.fields["category"].queryset = selectable(CategoryKind.INCOME)


class PayForm(IdempotentForm):
    """Pagar ou receber (F-031). O botão principal ignora o que estiver em "outro valor"."""

    ALTERNATIVES = ("amount", "late_fee", "excess_kind", "close_reason")

    account = forms.ModelChoiceField(label="Conta", queryset=active_accounts(), empty_label=None)
    on = forms.DateField(label="Data", widget=DateInput())
    amount = MoneyField(label="Valor", required=False)
    late_fee = MoneyField(label="Juros e multa", required=False)
    excess_kind = forms.ChoiceField(
        label="Se passar do valor da conta, o excedente é",
        choices=[("", "Não passa"), *ExcessKind.choices],
        required=False,
    )
    close_reason = forms.CharField(
        label="Encerrar com valor menor (motivo)",
        max_length=200,
        required=False,
        help_text="Preencha se a conta veio menor e nada mais será pago.",
    )

    def __init__(self, *args, remaining=None, incoming=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.remaining = remaining
        self.incoming = incoming
        self.full = self.is_bound and "full" in self.data
        self.fields["account"].queryset = active_accounts()
        self.initial.setdefault("on", ledger.today())
        if incoming:
            for name in ("late_fee", "excess_kind", "close_reason"):
                del self.fields[name]
            self.fields["account"].label = "Entra em"

    def clean(self):
        data = super().clean()
        if self.full:
            for name in self.ALTERNATIVES:
                self._errors.pop(name, None)
                data[name] = None
            data["amount"] = self.remaining
        elif not data.get("amount") and "amount" not in self.errors:
            self.add_error("amount", "Informe o valor.")
        return data


class ActualForm(StyledForm):
    amount = MoneyField(label="Valor real")


class ScheduleForm(StyledForm):
    debit_date = forms.DateField(label="Data do débito", widget=DateInput())


class ReasonForm(StyledForm):
    reason = forms.CharField(label="Motivo", max_length=200)


class RuleForm(Sectioned, StyledForm):
    advanced = ("value_type", "interval", "end_date", "remaining_count", "anticipates")

    name = forms.CharField(label="Nome", max_length=120)
    kind = forms.ChoiceField(
        label="Tipo", choices=[("bill", "Conta a pagar"), ("income", "Receita")]
    )
    amount = MoneyField(label="Valor")
    frequency = forms.ChoiceField(
        label="Repete", choices=Frequency.choices, initial=Frequency.MONTHLY
    )
    day_rule = forms.ChoiceField(label="Dia", choices=DayRule.choices)
    day_value = forms.IntegerField(
        label="Número do dia",
        min_value=1,
        max_value=31,
        required=False,
        help_text="Dia do mês ou qual dia útil. Não se aplica a último dia.",
    )
    category = forms.ModelChoiceField(
        label="Categoria", queryset=Category.objects.none(), empty_label="Escolha a categoria"
    )
    account = forms.ModelChoiceField(label="Conta", queryset=active_accounts(), empty_label=None)
    start_date = forms.DateField(label="Começa em", widget=DateInput())
    value_type = forms.ChoiceField(label="Tipo de valor", choices=VALUE_TYPES)
    interval = forms.IntegerField(
        label="A cada quantos meses",
        min_value=1,
        max_value=60,
        initial=1,
        help_text="Só para a opção A cada N meses.",
    )
    end_date = forms.DateField(label="Termina em", widget=DateInput(), required=False)
    remaining_count = forms.IntegerField(
        label="Número de ocorrências", min_value=1, max_value=600, required=False
    )
    anticipates = forms.BooleanField(label="Antecipa se cair em dia não útil", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = active_accounts()
        expense = selectable(CategoryKind.EXPENSE).values_list("pk", flat=True)
        income = selectable(CategoryKind.INCOME).values_list("pk", flat=True)
        self.fields["category"].queryset = Category.objects.filter(pk__in=[*expense, *income])

    def clean(self):
        data = super().clean()
        category = data.get("category")
        kind = data.get("kind")
        if category is not None and kind is not None:
            expected = CategoryKind.INCOME if kind == "income" else CategoryKind.EXPENSE
            if category.kind != expected:
                word = "receita" if kind == "income" else "despesa"
                self.add_error("category", f"Escolha uma categoria de {word}.")
        return data


class RuleEditForm(RuleForm):
    """Alterar recorrência (F-033): tipo e início não mudam; vale de uma data em diante."""

    from_date = forms.DateField(
        label="Vale a partir de",
        widget=DateInput(),
        help_text="O que venceu antes ou já foi pago fica como está.",
    )

    def __init__(self, *args, rule, **kwargs):
        super().__init__(*args, **kwargs)
        self.rule = rule
        del self.fields["start_date"]
        self.fields["kind"].required = False
        self.fields["kind"].widget = forms.HiddenInput()
        if rule.kind == "consortium":
            del self.fields["category"]
            del self.fields["value_type"]
            self.fields["kind"].choices = [("consortium", "Consórcio")]

    def clean(self):
        data = super().clean()
        data["kind"] = self.rule.kind
        return data


class MoneySettingsForm(StyledForm):
    minimum = MoneyField(
        label="Mínimo de segurança",
        required=False,
        help_text="Fica de fora do que você pode gastar. Deixe em branco para não usar.",
    )
    horizon_mode = forms.ChoiceField(
        label='"Pode gastar" conta até',
        choices=[("next_salary", "O próximo salário"), ("month_end", "O fim do mês")],
    )


class HolidayForm(StyledForm):
    date = forms.DateField(label="Data", widget=DateInput())
    name = forms.CharField(label="Nome", max_length=80)
    affects_salary = forms.BooleanField(
        label="Conta para o dia do salário", required=False, initial=True
    )
    affects_banking = forms.BooleanField(
        label="Conta para vencimentos", required=False, initial=True
    )
