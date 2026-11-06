"""Casos de borda de Money, arredondamento e escala (cobertura ≥ 95%, testing-plan.md §4)."""

import pytest

from apps.money import Money, quantize_cents, scale_legs


def test_zero_e_sinais():
    assert Money.zero() == Money(0)
    assert Money.zero().is_zero
    assert Money(-1).is_negative and not Money(-1).is_positive


def test_operacoes_com_outros_tipos_sao_recusadas():
    with pytest.raises(TypeError):
        Money(1) + 1
    with pytest.raises(TypeError):
        Money(1) - 1
    with pytest.raises(TypeError):
        Money.sum([Money(1), 2])


def test_quantize_so_aceita_decimal():
    with pytest.raises(TypeError):
        quantize_cents("0.01")


def test_escala_com_residuo_de_arredondamento():
    # 3 × ½ = 1,5 → 2 em cada perna positiva; o resíduo vai para a maior perna.
    assert scale_legs([3, 3, -6], 1, 2) == [2, 2, -4]
