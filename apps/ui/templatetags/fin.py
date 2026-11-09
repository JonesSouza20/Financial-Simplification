"""Filtros e ícones de template (ui-ux-specification.md §4, §7, §9)."""

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.money import Money

register = template.Library()

# Ícones próprios, traço reto de 1,75 px (design-study.md §12).
ICONS = {
    "home": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v9.5h13V10"/>',
    "list": '<path d="M8 6h12M8 12h12M8 18h12"/><path d="M3 6h2"/>'
    '<path d="M3 12h2"/><path d="M3 18h2"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "back": '<path d="M8 5h13v14H8l-6-7z"/><path d="M12 9.5l5 5M17 9.5l-5 5"/>',
    "wallet": '<rect x="3" y="6" width="18" height="13"/><path d="M16 12.5h2.5"/>'
    '<path d="M3 9h18"/>',
    "tag": '<path d="M3 12V4h8l9 9-8 8z"/><circle cx="7.5" cy="8.5" r="1.25"/>',
    "shield": '<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8 7.5 9.5 4.3-1.5 7.5-5 7.5-9.5V6z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4'
    'M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "logout": '<path d="M15 12H4M8 8l-4 4 4 4"/><path d="M13 4h6v16h-6"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7"/>',
    "alert": '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.5"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "card": '<rect x="2.5" y="5.5" width="19" height="13"/><path d="M2.5 10h19M6 15h4"/>',
    "users": '<circle cx="9" cy="8" r="3.25"/><path d="M3 19c.8-3.2 3.2-5 6-5s5.2 1.8 6 5"/>'
    '<path d="M16 5.2a3 3 0 0 1 0 5.6M18 14.3c1.6.7 2.6 2.3 3 4.7"/>',
    "debt": '<path d="M4 19h16M6 16V9M10 16V9M14 16V9M18 16V9M3 9l9-5 9 5"/>',
    "bolt": '<path d="M13.5 2.5 6 13.5h6l-1.5 8L18 10.5h-6z"/>',
    "drop": '<path d="M12 3.5c3.5 4.5 6 7.4 6 10.7a6 6 0 0 1-12 0c0-3.3 2.5-6.2 6-10.7z"/>',
    "flame": '<path d="M12 3c.6 3.2 5.5 5.4 5.5 10.5a5.5 5.5 0 0 1-11 0c0-2.3 1.2-3.8 2.5-5 '
    '.3 1.6 1 2.5 2 3 .2-3 .1-5.8 1-8.5z"/>',
    "wifi": '<path d="M3 9.5c5.2-4.5 12.8-4.5 18 0M6.8 14c3-2.4 7.4-2.4 10.4 0M12 18.5v.5"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19"/><path d="M11 18.5h2"/>',
    "meal": '<path d="M7 3v7a2.5 2.5 0 0 0 5 0V3M9.5 3v18"/>'
    '<path d="M17 3c-2 1.5-2.5 4-2.5 7 0 1.5 1 2.5 2.5 2.5V21"/>',
    "market": '<path d="M3 4h3l2.2 11h10L20 7.5H6.8"/><path d="M9.5 19.5v.5M17 19.5v.5"/>',
    "bus": '<rect x="4" y="3.5" width="16" height="14"/>'
    '<path d="M4 11h16M7.5 17.5V20M16.5 17.5V20"/>',
    "car": '<path d="M3 14.5 5.2 8h13.6l2.2 6.5v4.5H3zM6.5 19v2M17.5 19v2M3 14.5h18"/>',
    "income": '<path d="M12 20V4.5M6 10.5l6-6 6 6"/>',
    "other": '<rect x="4.5" y="4.5" width="15" height="15"/><path d="M8.5 12h7"/>',
}


@register.simple_tag
def icon(name, size=20, label=""):
    paths = ICONS.get(name, "")
    aria = format_html('role="img" aria-label="{}"', label) if label else 'aria-hidden="true"'
    return mark_safe(  # noqa: S308 - SVG fixo definido acima, sem dados do usuário
        f'<svg width="{int(size)}" height="{int(size)}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.75" stroke-linecap="square" '
        f'stroke-linejoin="miter" {aria}>{paths}</svg>'
    )


@register.filter
def brl(value):
    """Money ou centavos → 'R$ 1.234,56'."""
    if isinstance(value, Money):
        return value.format_brl()
    if isinstance(value, int):
        return Money(value).format_brl()
    return value


@register.filter
def num(value):
    """Valor sem o símbolo: '1.234,56'. Usado em listas e nos números grandes."""
    money = value if isinstance(value, Money) else Money(int(value or 0))
    return money.format_brl().replace("R$ ", "")


@register.filter
def tone(value):
    """Cor representa estado, não sinal (design-study.md §9): só saldo negativo pede atenção."""
    cents = value.cents if isinstance(value, Money) else int(value or 0)
    return "text-negative" if cents < 0 else ""


@register.filter
def signed(value):
    """Valor com sinal sempre visível: +R$ 50,00 ou −R$ 35,00 (RNF-07)."""
    money = value if isinstance(value, Money) else Money(int(value or 0))
    return f"+{money.format_brl()}" if money.is_positive else money.format_brl()
