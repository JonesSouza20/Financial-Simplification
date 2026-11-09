"""Categorias mais usadas no topo da lista do Lançar (design-study.md §11)."""

import datetime

from apps.entries import services as entries
from apps.entries.forms import EntryForm
from apps.entries.services import EXPENSE, EntryInput
from apps.money import Money


def spend(fin, category, times):
    for _ in range(times):
        entries.record(
            EntryInput(
                kind=EXPENSE,
                amount=Money(1000),
                account=fin.corrente,
                on=datetime.date(2026, 11, 10),
                category=category,
            )
        )


def test_mais_usadas_vem_primeiro_sem_repetir(fin, cats, on_20_11):
    spend(fin, cats.mercado, 3)
    spend(fin, cats.aluguel, 1)
    choices = list(EntryForm().fields["expense_category"].choices)
    assert choices[1][0] == "Mais usadas"
    assert [label for _, label in choices[1][1]][0].endswith("Mercado")
    used = {pk for pk, _ in choices[1][1]}
    assert not used & {pk for pk, _ in choices[2][1]}


def test_sem_historico_mantem_a_lista(fin, on_20_11):
    assert not any(c[0] == "Mais usadas" for c in EntryForm().fields["expense_category"].choices)
