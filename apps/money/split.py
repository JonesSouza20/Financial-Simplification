"""Rateio de parcelas (RN-005) e escala proporcional de pernas (estornos parciais, RN-121)."""

from __future__ import annotations

from typing import Literal

from .money import Money
from .rounding import round_half_up_int


def split_installments(
    total: Money, count: int, remainder_on: Literal["first", "last"] = "first"
) -> list[Money]:
    """Divide `total` em `count` parcelas.

    Valor-base = total ÷ n, truncado em centavos; a diferença vai para a primeira parcela
    (ou para a última, se configurado). Ex.: 100,00 em 3x = 33,34 + 33,33 + 33,33.
    """
    if type(count) is not int or count < 1:
        raise ValueError("O número de parcelas deve ser inteiro e maior que zero.")
    if total.cents <= 0:
        raise ValueError("O total parcelado deve ser maior que zero.")
    base = total.cents // count
    if base == 0:
        raise ValueError("Cada parcela precisa ser de pelo menos R$ 0,01.")
    parts = [base] * count
    remainder = total.cents - base * count
    parts[0 if remainder_on == "first" else -1] += remainder
    return [Money(p) for p in parts]


def scale_legs(amounts: list[int], numerator: int, denominator: int) -> list[int]:
    """Escala pernas (que somam zero) pela fração numerator/denominator, mantendo a soma zero.

    Cada perna é arredondada meio para cima; o resíduo do arredondamento vai para a perna de
    maior valor absoluto. Nenhuma perna resultante muda de sinal.
    """
    if sum(amounts) != 0:
        raise ValueError("As pernas precisam somar zero.")
    if not 0 < numerator <= denominator:
        raise ValueError("A fração precisa estar entre 0 (exclusive) e 1 (inclusive).")
    scaled = [round_half_up_int(a * numerator, denominator) for a in amounts]
    residue = sum(scaled)
    if residue:
        largest = max(range(len(scaled)), key=lambda i: abs(scaled[i]))
        scaled[largest] -= residue
    return scaled
