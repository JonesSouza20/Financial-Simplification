"""Configuração dos avisos (RF-ALE-03; security-plan.md §5: pede a senha)."""

from django import forms

from apps.ui.forms import StyledForm

from .telegram import TOKEN_RE

HOURS = [(hour, f"{hour:02d}:00") for hour in range(24)]


class AlertSettingsForm(StyledForm):
    token = forms.CharField(
        label="Token do bot",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "off"}),
        help_text="Fica no cofre do Windows. Deixe em branco para manter o atual.",
    )
    chat_id = forms.RegexField(
        label="Número do chat", regex=r"^-?\d{1,20}$", max_length=21, strip=True
    )
    days_before = forms.IntegerField(
        label="Avisar quantos dias antes",
        min_value=0,
        max_value=30,
        help_text="Além do aviso no dia do vencimento, às 08:00.",
    )
    quiet_start = forms.TypedChoiceField(label="Silêncio começa", choices=HOURS, coerce=int)
    quiet_end = forms.TypedChoiceField(
        label="Silêncio termina",
        choices=HOURS,
        coerce=int,
        help_text="Avisos de segurança chegam mesmo durante o silêncio.",
    )
    password = forms.CharField(
        label="Sua senha de login",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_token(self):
        token = self.cleaned_data["token"].strip()
        if token and not TOKEN_RE.fullmatch(token):
            raise forms.ValidationError("Esse token não tem o formato que o BotFather entrega.")
        return token
