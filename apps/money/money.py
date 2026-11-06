"""Tipo Money: valor monetário em centavos inteiros (RN-001)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .rounding import quantize_cents

MINUS = "−"  # sinal de menos tipográfico usado na interface (ui-ux-specification.md §7)


class MoneyParseError(ValueError):
    """Texto que não representa um valor em reais no formato brasileiro."""


_PT_BR = re.compile(
    r"^(?P<sign>[-−]?)\s*(?:R\$\s*)?"
    r"(?P<int>\d{1,3}(?:\.\d{3})+|\d+)"
    r"(?:,(?P<frac>\d{1,2}))?$"
)


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """Valor em centavos. Só aceita `int`; nunca ponto flutuante."""

    cents: int

    def __post_init__(self) -> None:
        if type(self.cents) is not int:  # exclui bool, Decimal e qualquer ponto flutuante
            raise TypeError("Money aceita apenas centavos inteiros (int).")

    # Construção -----------------------------------------------------------------

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_decimal(cls, reais: Decimal) -> Money:
        """Converte reais em Decimal para centavos, com ROUND_HALF_UP."""
        cents = quantize_cents(reais).scaleb(2)
        return cls(int(cents))

    @classmethod
    def parse(cls, text: str) -> Money:
        """Lê valor no formato pt-BR: '1.234,56', 'R$ 45,9', '-12,30', '1234'."""
        cleaned = text.strip().replace(" ", " ")
        match = _PT_BR.match(cleaned)
        if not match:
            raise MoneyParseError(f"Valor inválido: {text!r}. Use o formato 1.234,56.")
        integer = int(match["int"].replace(".", ""))
        frac = (match["frac"] or "0").ljust(2, "0")
        cents = integer * 100 + int(frac)
        return cls(-cents if match["sign"] else cents)

    @classmethod
    def from_typed_digits(cls, digits: str) -> Money:
        """Entrada da interface em centavos, da direita para a esquerda: '4590' → R$ 45,90."""
        if not digits.isdigit():
            raise MoneyParseError("Digite apenas números.")
        return cls(int(digits))

    # Conversão ------------------------------------------------------------------

    def to_decimal(self) -> Decimal:
        return Decimal(self.cents).scaleb(-2)

    def format_brl(self) -> str:
        """'R$ 1.234,56' ou '−R$ 1.234,56'."""
        sign = MINUS if self.cents < 0 else ""
        reais, cents = divmod(abs(self.cents), 100)
        grouped = f"{reais:,}".replace(",", ".")
        return f"{sign}R$ {grouped},{cents:02d}"

    def __str__(self) -> str:
        return self.format_brl()

    # Aritmética -----------------------------------------------------------------

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.cents - other.cents)

    def __neg__(self) -> Money:
        return Money(-self.cents)

    def __abs__(self) -> Money:
        return Money(abs(self.cents))

    def __mul__(self, factor: int) -> Money:
        if type(factor) is not int:
            return NotImplemented
        return Money(self.cents * factor)

    __rmul__ = __mul__

    @property
    def is_zero(self) -> bool:
        return self.cents == 0

    @property
    def is_positive(self) -> bool:
        return self.cents > 0

    @property
    def is_negative(self) -> bool:
        return self.cents < 0

    @staticmethod
    def sum(values) -> Money:
        total = 0
        for value in values:
            if not isinstance(value, Money):
                raise TypeError("Money.sum aceita apenas Money.")
            total += value.cents
        return Money(total)
