"""Arquivos estáticos servidos em produção pelo próprio processo (ADR-037).

O `live_server` dos testes de ponta a ponta serve estáticos sozinho, por isso este teste
usa o cliente comum com `DEBUG=False` e a pasta gerada pelo `collectstatic`.
"""

import pytest
from django.core.management import call_command
from django.test import Client


@pytest.mark.django_db
def test_css_e_scripts_sem_login_em_producao(settings, tmp_path):
    settings.DEBUG = False
    settings.WHITENOISE_USE_FINDERS = False  # como em produção: só o que o collectstatic gerou
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    call_command("collectstatic", interactive=False, verbosity=0)
    client = Client()
    for path in ("/static/css/app.css", "/static/js/app.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert b"".join(response.streaming_content)
    assert client.get("/").status_code == 302  # o resto continua exigindo login
