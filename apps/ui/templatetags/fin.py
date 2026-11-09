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
def tone(value):
    """Cor representa estado, não sinal (design-study.md §9): só saldo negativo pede atenção."""
    cents = value.cents if isinstance(value, Money) else int(value or 0)
    return "text-negative" if cents < 0 else ""


@register.filter
def signed(value):
    """Valor com sinal sempre visível: +R$ 50,00 ou −R$ 35,00 (RNF-07)."""
    money = value if isinstance(value, Money) else Money(int(value or 0))
    return f"+{money.format_brl()}" if money.is_positive else money.format_brl()
