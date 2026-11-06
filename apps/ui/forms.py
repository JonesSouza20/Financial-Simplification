"""Campos de formulário compartilhados."""

import uuid

from django import forms

from apps.money import Money, MoneyParseError


class MoneyField(forms.CharField):
    """Valor em reais no formato pt-BR (1.234,56). Devolve Money."""

    def __init__(self, *, allow_negative=False, **kwargs):
        self.allow_negative = allow_negative
        kwargs.setdefault("label", "Valor")
        kwargs.setdefault(
            "widget",
            forms.TextInput(
                attrs={
                    "inputmode": "decimal",
                    "autocomplete": "off",
                    "placeholder": "0,00",
                    "data-money": "1",
                }
            ),
        )
        super().__init__(**kwargs)

    def to_python(self, value):
        value = super().to_python(value)
        if value in self.empty_values:
            return None
        try:
            money = Money.parse(value)
        except MoneyParseError as exc:
            raise forms.ValidationError("Valor inválido. Use o formato 1.234,56.") from exc
        if money.is_negative and not self.allow_negative:
            raise forms.ValidationError("Informe um valor positivo.")
        return money


class StyledForm(forms.Form):
    """Aplica as classes visuais da ui-ux-specification.md §9 aos campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput | forms.RadioSelect | forms.HiddenInput):
                continue
            widget.attrs["class"] = (widget.attrs.get("class", "") + " input").strip()


class IdempotentForm(StyledForm):
    """Formulário com chave de idempotência gerada ao abrir a tela (RN-170)."""

    idempotency_key = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("idempotency_key", uuid.uuid4().hex)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)
