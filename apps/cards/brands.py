"""Banco e cor do cartão desenhado na tela (ADR-043). Só aparência: não entra em cálculo.

Os logotipos são marcas dos bancos e ficam fora do repositório: `ops/logos_bancos.py` baixa
e limpa os arquivos. Sem eles, o cartão aparece só com a cor.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class Bank:
    name: str
    color: str  # cor do cartão quando a pessoa não escolhe outra
    white_logo: bool = False  # logotipo branco vai direto no cartão; os demais num selo branco


BANKS = {
    "nubank": Bank("Nubank", "#820AD1", white_logo=True),
    "itau": Bank("Itaú", "#B85300"),
    "bradesco": Bank("Bradesco", "#CC092F"),
    "santander": Bank("Santander", "#CC0000"),
    "bb": Bank("Banco do Brasil", "#F5D90A"),
    "caixa": Bank("Caixa", "#005CA9"),
    "inter": Bank("Inter", "#B35400"),
    "c6": Bank("C6 Bank", "#1F1F1F", white_logo=True),
    "btg": Bank("BTG Pactual", "#0B2D5C"),
    "mercadopago": Bank("Mercado Pago", "#0074B7"),
    "picpay": Bank("PicPay", "#0B7D3B"),
    "neon": Bank("Neon", "#00769A"),
    "pagbank": Bank("PagBank", "#1E1E1E"),
    "sicredi": Bank("Sicredi", "#2E7A0C"),
    "sicoob": Bank("Sicoob", "#003641"),
    "pan": Bank("Pan", "#00739E"),
    "xp": Bank("XP", "#111111"),
}

COLORS = {
    "grafite": ("Grafite", "#2A2E34"),
    "cobalto": ("Cobalto", "#1B3FAB"),
    "verde": ("Verde", "#1D7A47"),
    "vinho": ("Vinho", "#7A1E2E"),
    "roxo": ("Roxo", "#5B2C9E"),
    "petroleo": ("Petróleo", "#0F5C63"),
    "laranja": ("Laranja", "#B85300"),
    "amarelo": ("Amarelo", "#F5D90A"),
    "preto": ("Preto", "#111111"),
}
LIGHT = {"#F5D90A"}  # cores claras levam texto escuro, para manter o contraste

BANK_CHOICES = [("", "Outro ou não informar")] + sorted(
    ((slug, bank.name) for slug, bank in BANKS.items()), key=lambda item: item[1]
)
COLOR_CHOICES = [("", "Cor do banco")] + [(slug, name) for slug, (name, _) in COLORS.items()]


@cache
def has_logo(slug: str) -> bool:
    return (Path(settings.BASE_DIR) / "static" / "img" / "bancos" / f"{slug}.svg").is_file()


def face(card) -> dict:
    """Classe de cor, logotipo e se o texto do cartão é escuro."""
    bank = BANKS.get(card.bank or "")
    logo = bool(bank) and has_logo(card.bank)
    if card.color in COLORS:
        key, hex_color = f"c-{card.color}", COLORS[card.color][1]
    elif bank is not None:
        key, hex_color = f"b-{card.bank}", bank.color
    else:
        key, hex_color = "c-grafite", COLORS["grafite"][1]
    return {
        "css": f"face-{key}",
        "dark_text": hex_color in LIGHT,
        "logo": f"img/bancos/{card.bank}.svg" if logo else "",
        "badge": logo and not bank.white_logo,
        "bank_name": bank.name if bank else "",
    }


def css() -> str:
    """Regras de cor de cada cartão, geradas uma vez para o CSS (a CSP não aceita style="")."""
    rules = [f".face-b-{slug}{{--face:{bank.color}}}" for slug, bank in BANKS.items()]
    rules += [f".face-c-{slug}{{--face:{hex_color}}}" for slug, (_, hex_color) in COLORS.items()]
    return "\n".join(rules)
