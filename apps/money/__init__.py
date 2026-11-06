"""Dinheiro em centavos inteiros, arredondamento e rateio (RN-001 a RN-005, ADR-002, ADR-026).

Código puro, sem banco de dados.
"""

from .money import Money, MoneyParseError
from .rounding import quantize_cents, round_half_up_int
from .split import scale_legs, split_installments

__all__ = [
    "Money",
    "MoneyParseError",
    "quantize_cents",
    "round_half_up_int",
    "scale_legs",
    "split_installments",
]
