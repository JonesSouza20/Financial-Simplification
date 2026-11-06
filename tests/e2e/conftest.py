"""Ponta a ponta com Playwright (testing-plan.md §12). Rodar com: uv run pytest -m e2e"""

import os

import pytest

# O Playwright síncrono mantém um loop de eventos na thread principal; o Django precisa
# disso liberado para acessar o banco nos testes (só em teste).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

MOBILE = {"width": 390, "height": 844}


@pytest.fixture
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": MOBILE,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
    }


@pytest.fixture
def app(committed_db, live_server, user, fin, page):
    """Servidor real + navegador já autenticado com senha."""
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{live_server.url}/acesso/entrar/")
    page.get_by_label("Senha").fill("uma frase de teste bem longa")
    page.get_by_role("button", name="Entrar").click()
    page.wait_for_url(f"{live_server.url}/")
    page.app_errors = errors
    page.base = live_server.url
    return page
