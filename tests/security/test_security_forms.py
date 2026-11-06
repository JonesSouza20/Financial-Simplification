"""Validações dos formulários de acesso (security-plan.md §3.1, §3.4)."""

import pytest

from apps.security.forms import ChangePasswordForm, DeviceForm, SetupForm

GOOD = "uma frase de teste bem longa"


@pytest.mark.django_db
def test_senhas_diferentes_na_configuracao():
    form = SetupForm({"password": GOOD, "confirm": GOOD + "x"})
    assert not form.is_valid() and "não são iguais" in str(form.errors)


@pytest.mark.django_db
def test_senha_curta_recusada():
    form = SetupForm({"password": "curta", "confirm": "curta"})
    assert not form.is_valid()


@pytest.mark.parametrize(
    ("pin", "confirm", "message"),
    [
        ("48a915", "48a915", "6 números"),
        ("111111", "111111", "6 números"),
        ("482915", "482916", "não são iguais"),
    ],
)
def test_pin_invalido(pin, confirm, message):
    form = DeviceForm({"name": "Celular", "pin": pin, "confirm": confirm})
    assert not form.is_valid() and message in str(form.errors)


@pytest.mark.django_db
def test_troca_de_senha_com_confirmacao_diferente():
    form = ChangePasswordForm({"current": GOOD, "new": GOOD + "!", "confirm": GOOD + "?"})
    assert not form.is_valid() and "não são iguais" in str(form.errors)
