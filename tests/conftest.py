"""Configuração comum dos testes (testing-plan.md §3)."""

import datetime
import os
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import keyring
import keyring.backend
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


PASSWORD = "uma frase de teste bem longa"  # noqa: S105 - só em testes


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user("usuario", password=PASSWORD)


@pytest.fixture
def web(client, user):
    """Cliente autenticado com senha, como no login real."""
    response = client.post("/acesso/entrar/", {"password": PASSWORD})
    assert response.status_code == 302, response.content
    return client


@pytest.fixture
def fin(db, on_20_11):
    """Contas financeiras do cadastro comum, abertas em 01/11/2026 com saldo zero."""
    from apps.accounts.services import create_account
    from apps.money import Money

    def make(name, account_type, asset_class, cents=0):
        return create_account(
            name=name,
            account_type=account_type,
            asset_class=asset_class,
            opening_balance=Money(cents),
            opening_date=datetime.date(2026, 11, 1),
        )

    return SimpleNamespace(
        corrente=make("Corrente", "checking", "free"),
        digital=make("Digital", "digital", "free"),
        reserva=make("Reserva", "reserve", "reserve"),
        vr=make("VR/VA", "benefit", "benefit"),
        make=make,
    )


@pytest.fixture
def cats(db):
    from apps.categories.models import Category

    def get(name, kind="expense"):
        return Category.objects.get(name=name, kind=kind)

    return SimpleNamespace(
        mercado=get("Mercado"),
        aluguel=get("Aluguel"),
        eletronicos=get("Eletrônicos"),
        salario=get("Salário", "income"),
        beneficios=get("Benefícios", "income"),
        get=get,
    )


@pytest.fixture
def card_a(db):
    """Cartão A do cadastro comum: limite 5.000,00, fecha dia 25, vence dia 5."""
    from apps.cards.services import create_card
    from apps.money import Money

    return create_card(name="Cartão A", credit_limit=Money(500000), closing_day=25, due_day=5)


@pytest.fixture
def card_b(db):
    """Cartão B do cadastro comum: limite 3.000,00, fecha dia 1, vence dia 10."""
    from apps.cards.services import create_card
    from apps.money import Money

    return create_card(name="Cartão B", credit_limit=Money(300000), closing_day=1, due_day=10)


@pytest.fixture
def ana(db):
    from apps.persons.services import get_or_create

    return get_or_create("Ana")


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
        # Tabelas de outros módulos referenciam transações; o flush do Django as limpa depois.
        cursor.execute("PRAGMA foreign_keys = OFF")
        for table in (
            "transaction_note",
            "transaction_link",
            "ledger_posting",
            "idempotency_record",
            "audit_log",
            "ledger_transaction",
        ):
            cursor.execute(f"DELETE FROM {table}")  # noqa: S608
        cursor.execute("PRAGMA foreign_keys = ON")
    db_triggers.install(connection)


class MemoryKeyring(keyring.backend.KeyringBackend):
    """Cofre de segredos em memória."""

    priority = 1

    def __init__(self):
        super().__init__()
        self.data = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        self.data.pop((service, username), None)


@pytest.fixture(autouse=True)
def _memory_keyring():
    """Nenhum teste lê ou grava o Cofre de Credenciais real do Windows. O update.ps1 roda a
    suíte no PC que guarda a senha de backup de verdade."""
    previous = keyring.get_keyring()
    memory = MemoryKeyring()
    keyring.set_keyring(memory)
    yield memory
    keyring.set_keyring(previous)
