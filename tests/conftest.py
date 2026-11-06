"""Configuração comum dos testes (testing-plan.md §3)."""

import datetime
import os
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import time_machine
from hypothesis import HealthCheck, settings

from apps.ledger import db_triggers

# Perfis do Hypothesis: "default" na execução diária; "thorough" (1.000 exemplos) nas portas.
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.register_profile(
    "thorough",
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def travel_to(day: datetime.date):
    """Congela o relógio ao meio-dia de São Paulo do dia indicado."""
    moment = datetime.datetime.combine(day, datetime.time(12, 0), tzinfo=SAO_PAULO)
    return time_machine.travel(moment, tick=False)


@pytest.fixture
def on_20_11():
    """Data da fotografia do S14: 20/11/2026."""
    with travel_to(datetime.date(2026, 11, 20)):
        yield datetime.date(2026, 11, 20)


@pytest.fixture
def accounts(db):
    """Contas contábeis mínimas do cadastro comum de reference-scenarios.md."""
    from apps.ledger.models import LedgerAccount

    def make(code, kind, name, asset_class=None):
        account, _ = LedgerAccount.objects.get_or_create(
            code=code, defaults={"kind": kind, "name": name, "asset_class": asset_class}
        )
        return account

    return SimpleNamespace(
        corrente=make("asset:fin:corrente", "asset", "Corrente", "free"),
        digital=make("asset:fin:digital", "asset", "Digital", "free"),
        reserva=make("asset:fin:reserva", "asset", "Reserva", "reserve"),
        vr=make("asset:fin:vr", "asset", "VR/VA", "benefit"),
        ana=make("asset:person:ana", "asset", "A receber: Ana", "receivable"),
        cartao_a=make("liability:card:a", "liability", "Cartão A"),
        emprestimo=make("liability:debt:emprestimo", "liability", "Empréstimo"),
        mercado=make("expense:cat:mercado", "expense", "Mercado"),
        eletronicos=make("expense:cat:eletronicos", "expense", "Eletrônicos"),
        restaurantes=make("expense:cat:restaurantes", "expense", "Restaurantes"),
        juros=make("expense:cat:juros", "expense", "Juros de dívidas"),
        salario=make("income:cat:salario", "income", "Salário"),
        abertura=make("equity:opening", "equity", "Patrimônio: Abertura"),
    )


@pytest.fixture
def committed_db(transactional_db):
    """Banco com commits reais (testes de concorrência).

    O `flush` do Django usa DELETE, que os gatilhos bloqueiam. Ao fim do teste, os gatilhos
    de exclusão são removidos só para limpar as tabelas do Ledger e recriados em seguida
    (database-design.md §15). Em produção eles nunca são removidos.
    """
    yield
    from django.db import connection

    db_triggers.uninstall(connection, db_triggers.DELETE_BLOCKERS)
    with connection.cursor() as cursor:
        for table in (
            "transaction_note",
            "transaction_link",
            "ledger_posting",
            "idempotency_record",
            "audit_log",
            "ledger_transaction",
        ):
            cursor.execute(f"DELETE FROM {table}")  # noqa: S608
    db_triggers.install(connection)
