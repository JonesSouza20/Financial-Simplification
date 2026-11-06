"""Arredondamento único do sistema: meio para cima (ROUND_HALF_UP), 28 dígitos (RN-004)."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

PRECISION = 28
CENT = Decimal("0.01")
UNIT = Decimal("1")


def quantize_cents(value: Decimal) -> Decimal:
    """Arredonda um valor em reais para centavos. Ex.: 0,005 → 0,01; −0,005 → −0,01."""
    if not isinstance(value, Decimal):
        raise TypeError("quantize_cents aceita apenas Decimal.")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return value.quantize(CENT, rounding=ROUND_HALF_UP)


def round_half_up_int(numerator: int, denominator: int) -> int:
    """Divide inteiros e arredonda o resultado para inteiro, meio para cima (longe do zero)."""
    if denominator == 0:
        raise ZeroDivisionError("denominador zero")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        result = (Decimal(numerator) / Decimal(denominator)).quantize(UNIT, rounding=ROUND_HALF_UP)
    return int(result)
