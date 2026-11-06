"""Ciclo de fatura (RN-070 a RN-073; S02)."""

import datetime

import pytest

from apps.cards import cycle

D = datetime.date


@pytest.mark.parametrize(
    ("purchase", "closing", "due", "expected"),
    [
        (D(2026, 11, 24), 25, 5, D(2026, 12, 5)),  # S02: antes do fechamento
        (D(2026, 11, 25), 25, 5, D(2027, 1, 5)),  # S02: no dia do fechamento vai para a próxima
        (D(2026, 12, 26), 25, 5, D(2027, 2, 5)),  # virada de ano
        (D(2026, 11, 1), 1, 10, D(2026, 12, 10)),  # Cartão B: compra no dia 1 vai para dezembro
        (D(2026, 11, 30), 1, 10, D(2026, 12, 10)),
        (D(2026, 12, 1), 1, 10, D(2027, 1, 10)),
        (D(2027, 2, 10), 31, 10, D(2027, 3, 10)),  # fechamento 31 em fevereiro vira 28
        (D(2027, 2, 28), 31, 10, D(2027, 4, 10)),  # no "dia 31" de fevereiro (28): próxima
    ],
)
def test_primeiro_vencimento(purchase, closing, due, expected):
    assert cycle.first_due(purchase, closing, due) == expected


def test_compra_no_fechamento_sem_regra_de_proxima():
    assert cycle.first_due(D(2026, 11, 25), 25, 5, goes_next=False) == D(2026, 12, 5)


def test_parcelas_seguintes_e_meses_curtos():
    first = D(2027, 1, 31)
    assert cycle.nth_due(first, 2, 31) == D(2027, 2, 28)
    assert cycle.nth_due(first, 3, 31) == D(2027, 3, 31)
    assert cycle.nth_due(D(2026, 12, 5), 3, 5) == D(2027, 2, 5)


def test_vencimento_no_mesmo_mes_quando_maior_que_fechamento():
    assert cycle.due_date_for(D(2026, 12, 1), 1, 10) == D(2026, 12, 10)
    assert cycle.due_date_for(D(2026, 11, 25), 25, 5) == D(2026, 12, 5)
