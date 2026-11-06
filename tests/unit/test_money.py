"""Tipo Money e arredondamento (RN-001, RN-004; testing-plan.md §8)."""

from decimal import Decimal

import pytest

from apps.money import Money, MoneyParseError, quantize_cents, round_half_up_int


def test_aceita_so_inteiros():
    assert Money(123).cents == 123
    for invalid in (Decimal("1"), True, "1"):
        with pytest.raises(TypeError):
            Money(invalid)


def test_recusa_ponto_flutuante():
    with pytest.raises(TypeError):
        Money(float("1"))  # o único float do projeto, para provar a recusa


def test_aritmetica():
    a, b = Money(1050), Money(250)
    assert a + b == Money(1300)
    assert a - b == Money(800)
    assert -a == Money(-1050)
    assert abs(Money(-5)) == Money(5)
    assert a * 3 == Money(3150) == 3 * a
    assert Money.sum([a, b, Money(0)]) == Money(1300)
    assert Money(1) > Money(0)


def test_multiplicacao_so_por_inteiro():
    with pytest.raises(TypeError):
        Money(100) * Decimal("1.5")


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "R$ 0,00"),
        (1, "R$ 0,01"),
        (-1, "−R$ 0,01"),
        (123456, "R$ 1.234,56"),
        (999999999, "R$ 9.999.999,99"),
        (-443940, "−R$ 4.439,40"),
    ],
)
def test_formatacao_pt_br(cents, text):
    assert Money(cents).format_brl() == text
    assert str(Money(cents)) == text


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("1.234,56", 123456),
        ("R$ 1.234,56", 123456),
        ("45,9", 4590),
        ("45", 4500),
        ("1234", 123400),
        ("-12,30", -1230),
        ("−12,30", -1230),
        (" R$ 930,00 ", 93000),
    ],
)
def test_leitura_pt_br(text, cents):
    assert Money.parse(text) == Money(cents)


@pytest.mark.parametrize("text", ["", "abc", "1,234.56", "12,345", "1.23,45", "R$"])
def test_leitura_invalida(text):
    with pytest.raises(MoneyParseError):
        Money.parse(text)


def test_digitacao_em_centavos():
    assert Money.from_typed_digits("4590") == Money(4590)
    with pytest.raises(MoneyParseError):
        Money.from_typed_digits("45,90")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.005", "0.01"),
        ("-0.005", "-0.01"),
        ("0.004", "0.00"),
        ("1234567890123.455", "1234567890123.46"),
    ],
)
def test_round_half_up(value, expected):
    assert quantize_cents(Decimal(value)) == Decimal(expected)


def test_from_decimal_arredonda_meio_para_cima():
    assert Money.from_decimal(Decimal("945.595")) == Money(94560)
    assert Money(94560).to_decimal() == Decimal("945.60")


def test_divisao_inteira_arredondada():
    assert round_half_up_int(5, 2) == 3
    assert round_half_up_int(-5, 2) == -3
    assert round_half_up_int(4, 3) == 1
    with pytest.raises(ZeroDivisionError):
        round_half_up_int(1, 0)
