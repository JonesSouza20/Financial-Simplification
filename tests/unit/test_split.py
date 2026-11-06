"""Rateio de parcelas e escala proporcional (RN-005, RN-121)."""

import pytest

from apps.money import Money, scale_legs, split_installments


def test_parcela_unica():
    assert split_installments(Money(12345), 1) == [Money(12345)]


def test_48_parcelas_somam_o_total():
    parts = split_installments(Money(100000), 48)
    assert len(parts) == 48
    assert Money.sum(parts) == Money(100000)
    assert parts[0] == Money(2099) and parts[1] == Money(2083)  # 2.083 × 48 + 16 de resto


def test_total_menor_que_numero_de_parcelas_e_recusado():
    with pytest.raises(ValueError, match="R\\$ 0,01"):
        split_installments(Money(2), 3)


@pytest.mark.parametrize("count", [0, -1])
def test_numero_de_parcelas_invalido(count):
    with pytest.raises(ValueError):
        split_installments(Money(100), count)


def test_total_zero_ou_negativo_recusado():
    with pytest.raises(ValueError):
        split_installments(Money(0), 2)


def test_escala_mantem_soma_zero_e_sinais():
    # Compra mista de 250,00: 100,00 próprio, 150,00 da Ana; estorno de 50,00.
    scaled = scale_legs([10000, 15000, -25000], 5000, 25000)
    assert scaled == [2000, 3000, -5000]
    odd = scale_legs([10000, 15000, -25000], 1, 3)
    assert sum(odd) == 0
    assert odd[0] > 0 and odd[1] > 0 and odd[2] < 0


def test_escala_recusa_pernas_desequilibradas_e_fracao_invalida():
    with pytest.raises(ValueError):
        scale_legs([1, 2], 1, 2)
    with pytest.raises(ValueError):
        scale_legs([1, -1], 3, 2)
