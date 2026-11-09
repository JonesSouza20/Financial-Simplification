"""Feriados pré-carregados (RN-092): nacionais, 9 de julho e os da capital de São Paulo.

Funções puras, sem banco. As datas móveis saem da Páscoa.
"""

from __future__ import annotations

import datetime

from .models import HolidayScope

FIXED = (
    (1, 1, "Confraternização Universal", HolidayScope.NATIONAL),
    (1, 25, "Aniversário de São Paulo", HolidayScope.MUNICIPAL),
    (4, 21, "Tiradentes", HolidayScope.NATIONAL),
    (5, 1, "Dia do Trabalho", HolidayScope.NATIONAL),
    (7, 9, "Revolução Constitucionalista", HolidayScope.STATE),
    (9, 7, "Independência do Brasil", HolidayScope.NATIONAL),
    (10, 12, "Nossa Senhora Aparecida", HolidayScope.NATIONAL),
    (11, 2, "Finados", HolidayScope.NATIONAL),
    (11, 15, "Proclamação da República", HolidayScope.NATIONAL),
    (11, 20, "Consciência Negra", HolidayScope.NATIONAL),
    (12, 25, "Natal", HolidayScope.NATIONAL),
)


def easter(year: int) -> datetime.date:
    """Domingo de Páscoa (algoritmo gregoriano anônimo: Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return datetime.date(year, month, day + 1)


def for_year(year: int) -> list[tuple[datetime.date, str, str]]:
    """Feriados do ano: (data, nome, abrangência). Sem repetir data."""
    sunday = easter(year)
    moving = [
        (sunday - datetime.timedelta(days=48), "Carnaval (segunda)", HolidayScope.CARNIVAL),
        (sunday - datetime.timedelta(days=47), "Carnaval (terça)", HolidayScope.CARNIVAL),
        (sunday - datetime.timedelta(days=2), "Sexta-feira Santa", HolidayScope.NATIONAL),
        (sunday + datetime.timedelta(days=60), "Corpus Christi", HolidayScope.MUNICIPAL),
    ]
    fixed = [(datetime.date(year, m, d), name, scope) for m, d, name, scope in FIXED]
    by_date = {when: (when, name, scope) for when, name, scope in [*fixed, *moving]}
    return [by_date[when] for when in sorted(by_date)]
