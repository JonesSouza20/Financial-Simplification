from django import forms
from django.contrib.auth import password_validation

from apps.ui.forms import StyledForm

from .devices import trivial_pin

PIN_FIELD = dict(
    min_length=6,
    max_length=6,
    widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
)


class SetupForm(StyledForm):
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)
    confirm = forms.CharField(label="Repita a senha", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("confirm"):
            raise forms.ValidationError("As senhas não são iguais.")
        if data.get("password"):
            password_validation.validate_password(data["password"])
        return data


class LoginForm(StyledForm):
    password = forms.CharField(
        label="Senha", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )
    trust_device = forms.BooleanField(
        label="Confiar neste aparelho e usar PIN nos próximos 30 dias", required=False
    )


class DeviceForm(StyledForm):
    name = forms.CharField(label="Nome do aparelho", max_length=60, initial="Meu celular")
    pin = forms.CharField(label="PIN de 6 dígitos", **PIN_FIELD)
    confirm = forms.CharField(label="Repita o PIN", **PIN_FIELD)

    def clean(self):
        data = super().clean()
        pin = data.get("pin") or ""
        if pin and (not pin.isdigit() or trivial_pin(pin)):
            raise forms.ValidationError(
                "Use 6 números, sem sequências (123456) nem repetições (000000)."
            )
        if pin != data.get("confirm"):
            raise forms.ValidationError("Os PINs não são iguais.")
        return data


class PinForm(StyledForm):
    pin = forms.CharField(label="PIN", **PIN_FIELD)


class ConfirmPasswordForm(StyledForm):
    """Operações sensíveis sempre pedem a senha (security-plan.md §3.4)."""

    password = forms.CharField(label="Sua senha", widget=forms.PasswordInput)


class ChangePasswordForm(StyledForm):
    current = forms.CharField(label="Senha atual", widget=forms.PasswordInput)
    new = forms.CharField(label="Nova senha", widget=forms.PasswordInput)
    confirm = forms.CharField(label="Repita a nova senha", widget=forms.PasswordInput)

    def clean(self):
        data = super().clean()
        if data.get("new") != data.get("confirm"):
            raise forms.ValidationError("As senhas novas não são iguais.")
        if data.get("new"):
            password_validation.validate_password(data["new"])
        return data
