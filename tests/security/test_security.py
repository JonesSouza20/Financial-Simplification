"""Segurança (testing-plan.md §9; security-plan.md §3, §8; ADR-019, ADR-035)."""

import datetime
import importlib
import time

import pytest
import time_machine
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from apps.ledger.models import AuditLog
from apps.security import devices
from apps.security.models import TrustedDevice
from tests.conftest import PASSWORD

PUBLIC = {
    "/acesso/configurar/",
    "/acesso/entrar/",
    "/acesso/pin/",
    "/manifest.webmanifest",
    "/sw.js",
}


def all_paths(resolver=None, prefix=""):
    resolver = resolver or get_resolver()
    for p in resolver.url_patterns:
        route = prefix + str(p.pattern).replace("<int:pk>", "1")
        if isinstance(p, URLResolver):
            yield from all_paths(p, route)
        elif isinstance(p, URLPattern):
            yield "/" + route


@pytest.mark.django_db
def test_toda_rota_exige_login(client, user):
    paths = sorted(set(all_paths()))
    assert len(paths) > 15
    for path in paths:
        if path in PUBLIC:
            continue
        response = client.get(path)
        assert response.status_code == 302 and "/acesso/entrar/" in response["Location"], path


@pytest.mark.django_db
def test_primeiro_acesso_cria_a_senha(client):
    assert client.get("/acesso/entrar/")["Location"] == "/acesso/configurar/"
    weak = client.post("/acesso/configurar/", {"password": "123", "confirm": "123"})
    assert weak.status_code == 200
    ok = client.post("/acesso/configurar/", {"password": PASSWORD, "confirm": PASSWORD})
    assert ok.status_code == 302
    assert client.get("/acesso/configurar/")["Location"] == "/acesso/entrar/"


@pytest.mark.django_db
def test_senha_guardada_com_argon2(user):
    assert user.password.startswith("argon2$argon2id$")


@pytest.mark.django_db
def test_cinco_senhas_erradas_bloqueiam(client, user):
    for _ in range(5):
        client.post("/acesso/entrar/", {"password": "errada"})
    blocked = client.post("/acesso/entrar/", {"password": PASSWORD})
    assert blocked.status_code == 403
    assert "15 minutos" in blocked.content.decode()
    assert AuditLog.objects.filter(action="lockout").exists()


@pytest.mark.django_db
def test_bloqueio_repetido_dobra(user):
    from apps.security.lockout import cooloff

    assert cooloff() == datetime.timedelta(minutes=15)
    for _ in range(2):
        AuditLog.objects.create(action="lockout", entity_type="auth_user", entity_id=0)
    assert cooloff() == datetime.timedelta(minutes=30)
    for _ in range(10):
        AuditLog.objects.create(action="lockout", entity_type="auth_user", entity_id=0)
    assert cooloff() == datetime.timedelta(hours=24)


def _expire(client, seconds_ago, key="last_activity"):
    session = client.session
    session[key] = int(time.time()) - seconds_ago
    session.save()


def test_sessao_ociosa_vai_para_login(web):
    _expire(web, 31 * 60)
    response = web.get("/contas/")
    assert response.status_code == 302 and response["Location"].startswith("/acesso/entrar/")


def test_expiracao_absoluta(web):
    _expire(web, 12 * 3600 + 1, key="auth_started")
    assert web.get("/contas/")["Location"].startswith("/acesso/entrar/")


def _trust(web, pin="482915"):
    response = web.post("/acesso/aparelhos/novo/", {"name": "Celular", "pin": pin, "confirm": pin})
    assert response.status_code == 302
    return TrustedDevice.objects.get(name="Celular")


def test_pin_reabre_sessao_e_troca_identificador(web):
    device = _trust(web)
    assert device.token_hash and "fin_device" in web.cookies
    _expire(web, 31 * 60)
    response = web.get("/contas/")
    assert response["Location"].startswith("/acesso/pin/")
    old_key = web.session.session_key
    ok = web.post("/acesso/pin/", {"pin": "482915", "next": "/contas/"})
    assert ok.status_code == 302 and ok["Location"] == "/contas/"
    assert web.session.session_key != old_key
    assert web.session["auth_method"] == "pin"


def test_pin_reabre_depois_da_expiracao_absoluta(web):
    _trust(web)
    _expire(web, 12 * 3600 + 1, key="auth_started")
    assert web.get("/contas/")["Location"].startswith("/acesso/pin/")


def test_cinco_pins_errados_revogam(web):
    device = _trust(web)
    web.post("/acesso/sair/")
    for _ in range(5):
        web.post("/acesso/pin/", {"pin": "000001"})
    device.refresh_from_db()
    assert device.revoked_at is not None
    assert web.get("/acesso/pin/")["Location"] == "/acesso/entrar/"


def test_token_vencido_exige_senha(web):
    _trust(web)
    web.post("/acesso/sair/")
    with time_machine.travel(timezone.now() + datetime.timedelta(days=31), tick=False):
        assert web.get("/acesso/pin/")["Location"] == "/acesso/entrar/"


def test_pin_trivial_recusado(web):
    response = web.post(
        "/acesso/aparelhos/novo/", {"name": "X", "pin": "123456", "confirm": "123456"}
    )
    assert response.status_code == 200
    assert not TrustedDevice.objects.exists()
    assert devices.trivial_pin("000000") and devices.trivial_pin("654321")
    assert not devices.trivial_pin("482915")


def test_confiar_aparelho_exige_sessao_aberta_com_senha(web):
    _trust(web)
    web.post("/acesso/sair/")
    web.post("/acesso/pin/", {"pin": "482915"})
    response = web.get("/acesso/aparelhos/novo/")
    assert response["Location"] == "/acesso/entrar/"


def test_revogar_exige_senha(web):
    device = _trust(web)
    web.post(f"/acesso/aparelhos/{device.pk}/revogar/", {"password": "errada"})
    device.refresh_from_db()
    assert device.revoked_at is None
    web.post(f"/acesso/aparelhos/{device.pk}/revogar/", {"password": PASSWORD})
    device.refresh_from_db()
    assert device.revoked_at is not None


def test_troca_de_senha_revoga_aparelhos(web):
    device = _trust(web)
    new = "outra frase de teste bem longa"
    web.post("/acesso/senha/", {"current": PASSWORD, "new": new, "confirm": new})
    device.refresh_from_db()
    assert device.revoked_at is not None
    assert web.get("/contas/").status_code == 200  # sessão atual continua


@pytest.mark.django_db
def test_post_sem_csrf_e_recusado(user):
    client = Client(enforce_csrf_checks=True)
    assert client.post("/acesso/entrar/", {"password": PASSWORD}).status_code == 403


@pytest.mark.django_db
def test_host_nao_permitido(client):
    assert client.get("/acesso/entrar/", HTTP_HOST="evil.example").status_code == 400


def test_cabecalhos_de_seguranca(web):
    response = web.get("/")
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["X-Frame-Options"] == "DENY"
    assert response["Cache-Control"] == "no-store"


def test_configuracao_de_producao(monkeypatch):
    monkeypatch.setenv("FINANCAS_SECRET_KEY", "x" * 60)
    monkeypatch.setenv("FINANCAS_TAILNET_HOST", "pc.exemplo.ts.net")
    prod = importlib.import_module("config.settings.prod")
    prod = importlib.reload(prod)
    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE
    assert prod.SECURE_HSTS_SECONDS > 0
    assert "pc.exemplo.ts.net" in prod.ALLOWED_HOSTS


def test_auditoria_nao_guarda_segredos(web):
    _trust(web)
    web.post("/acesso/pin/", {"pin": "482915"})
    dump = " ".join(str(a.after_json) + str(a.reason) for a in AuditLog.objects.all())
    for secret in (PASSWORD, "482915"):
        assert secret not in dump


@pytest.mark.django_db
def test_login_com_confiar_aparelho_leva_ao_pin(client, user):
    response = client.post("/acesso/entrar/", {"password": PASSWORD, "trust_device": "on"})
    assert response["Location"] == "/acesso/aparelhos/novo/"


def test_login_com_senha_renova_aparelho(web):
    device = _trust(web)
    TrustedDevice.objects.filter(pk=device.pk).update(
        expires_at=timezone.now() + datetime.timedelta(days=1)
    )
    web.post("/acesso/sair/")
    web.post("/acesso/entrar/", {"password": PASSWORD})
    device.refresh_from_db()
    assert device.expires_at > timezone.now() + datetime.timedelta(days=29)


def test_revogar_todos_exige_senha(web):
    _trust(web)
    web.post("/acesso/aparelhos/revogar-todos/", {"password": "errada"})
    assert TrustedDevice.objects.filter(revoked_at__isnull=True).count() == 1
    web.post("/acesso/aparelhos/revogar-todos/", {"password": PASSWORD})
    assert TrustedDevice.objects.filter(revoked_at__isnull=True).count() == 0


def test_troca_de_senha_com_senha_atual_errada(web, user):
    new = "outra frase de teste bem longa"
    page = web.post(
        "/acesso/senha/", {"current": "errada", "new": new, "confirm": new}, follow=True
    )
    assert "Não foi possível trocar a senha" in page.content.decode()
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
