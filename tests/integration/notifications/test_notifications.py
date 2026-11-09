"""Avisos no Telegram (F-080). Nenhum teste usa a rede: `urlopen` é sempre substituído."""

import datetime
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest
from django.contrib.auth.signals import user_login_failed
from django.utils import timezone

from apps.backup import secrets
from apps.backup.models import BackupRecord
from apps.money import Money
from apps.notifications import services, telegram
from apps.notifications.models import Notification
from apps.payables import services as payables
from apps.scheduler import jobs
from apps.scheduler.models import JobRun
from apps.security import devices
from apps.ui import models as prefs
from apps.ui.models import Setting
from tests.conftest import PASSWORD, SAO_PAULO, travel_to

D = datetime.date
TOKEN = "123456789:AAHsegredoDoBotQueNuncaPodeVazar_x-1"  # noqa: S105 - fictício
pytestmark = pytest.mark.usefixtures("on_20_11")


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def net(monkeypatch):
    """Registra os envios; qualquer chamada passa por aqui, nunca pela rede."""
    calls = []

    def fake(request, timeout=None):
        calls.append(request)
        return FakeResponse()

    monkeypatch.setattr(telegram, "urlopen", fake)
    return calls


@pytest.fixture
def setup_bot(db):
    secrets.put(secrets.TELEGRAM_TOKEN, TOKEN)
    prefs.put(telegram.CHAT_KEY, "777")
    BackupRecord.objects.create(trigger="daily", checks_passed=True, local_ok=True)


def at(day, hour):
    return datetime.datetime(day.year, day.month, day.day, hour, 0, tzinfo=SAO_PAULO)


def texts():
    return sorted(Notification.objects.values_list("summary", flat=True))


@pytest.fixture
def bill(fin, cats):
    return payables.create_bill(
        description="Aluguel",
        category=cats.aluguel,
        account=fin.corrente,
        amount=Money(150000),
        due_date=D(2026, 11, 23),
    )


def test_envia_para_o_chat_configurado(setup_bot, net):
    telegram.send("oi")
    assert net[0].full_url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert parse_qs(net[0].data.decode()) == {"chat_id": ["777"], "text": ["oi"]}


def test_sem_configuracao_nada_vai_para_a_fila(bill, net):
    assert services.collect() == "Telegram não configurado"
    assert not Notification.objects.exists() and not net


def test_avisa_tres_dias_antes_uma_vez(setup_bot, bill):
    services.collect()
    services.collect()
    assert texts() == ["Aluguel R$ 1.500,00 vence em 23/11 (segunda)."]


def test_fora_da_antecedencia_nao_avisa(setup_bot, fin, cats):
    payables.create_bill(
        description="Longe",
        category=cats.aluguel,
        account=fin.corrente,
        amount=Money(100),
        due_date=D(2026, 11, 24),
    )
    services.collect()
    assert not Notification.objects.exists()


def test_antecedencia_configuravel(setup_bot, bill):
    prefs.put(services.DAYS_KEY, 2)
    services.collect()
    assert not Notification.objects.exists()


def test_avisa_de_novo_no_dia(setup_bot, bill):
    services.collect()
    with travel_to(D(2026, 11, 23)):
        services.collect()
    assert Notification.objects.filter(kind="due").count() == 2


def test_atraso_no_dia_seguinte_uma_so_vez(setup_bot, bill):
    with travel_to(D(2026, 11, 24)):
        services.collect()
    with travel_to(D(2026, 11, 25)):
        services.collect()
    late = Notification.objects.filter(kind="overdue")
    assert [n.summary for n in late] == ["Atrasado: Aluguel R$ 1.500,00, venceu em 23/11."]


def test_conta_paga_ou_agendada_nao_avisa(setup_bot, bill, fin):
    payables.schedule(bill, debit_date=D(2026, 11, 23))
    services.collect()
    assert not Notification.objects.exists()
    bill.refresh_from_db()
    payables.unschedule(bill)
    bill.refresh_from_db()
    payables.pay(bill, amount=Money(150000), account=fin.corrente)
    services.collect()
    assert not [t for t in texts() if "Aluguel" in t]


def test_valor_estimado_diz_cerca_de(setup_bot, fin, cats):
    payables.create_bill(
        description="Luz",
        category=cats.aluguel,
        account=fin.corrente,
        amount=Money(18000),
        due_date=D(2026, 11, 22),
        value_type="variable",
    )
    services.collect()
    assert "Luz cerca de R$ 180,00 vence em 22/11 (domingo)." in texts()[-1]
    assert "Pode pagar até 23/11" in texts()[-1]


def test_silencio_segura_e_libera_depois(setup_bot, bill, net):
    services.collect()
    assert services.flush(at(D(2026, 11, 20), 23)) == 0 and not net
    assert services.flush(at(D(2026, 11, 21), 6)) == 0 and not net
    assert services.flush(at(D(2026, 11, 21), 7)) == 1
    assert len(net) == 1
    assert services.flush(at(D(2026, 11, 21), 8)) == 0


def test_seguranca_fura_o_silencio(setup_bot, net):
    services.enqueue("security", "Login bloqueado", "lock:1")
    assert services.flush(at(D(2026, 11, 20), 23)) == 1


@pytest.mark.parametrize(
    ("start", "end", "hour", "expected"),
    [(22, 7, 23, True), (22, 7, 3, True), (22, 7, 7, False), (9, 17, 12, True), (5, 5, 5, False)],
)
def test_janela_de_silencio(start, end, hour, expected):
    assert services.is_quiet(hour, start, end) is expected


def test_falha_tenta_de_novo_em_15_minutos(setup_bot, bill, monkeypatch, net):
    services.collect()
    noon = at(D(2026, 11, 20), 12)

    def fail(request, timeout=None):
        raise URLError("rede fora")

    monkeypatch.setattr(telegram, "urlopen", fail)
    assert services.flush(noon) == 0
    item = Notification.objects.get()
    assert item.status == "pending" and "rede fora" in item.last_error
    assert services.flush(noon + datetime.timedelta(minutes=5)) == 0
    monkeypatch.setattr(telegram, "urlopen", lambda r, timeout=None: FakeResponse())
    assert services.flush(noon + datetime.timedelta(minutes=16)) == 1


def test_aviso_velho_expira(setup_bot, bill):
    services.collect()
    assert services.flush(at(D(2026, 11, 22), 13)) == 0
    assert Notification.objects.get().status == "failed"


@pytest.mark.parametrize(
    "error",
    [
        URLError(f"falha em https://api.telegram.org/bot{TOKEN}/sendMessage"),
        OSError(f"conexão com bot{TOKEN} recusada"),
        HTTPError(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 500, "x", {}, None),
    ],
)
def test_token_nunca_aparece_em_erro(setup_bot, bill, monkeypatch, caplog, error):
    def fail(request, timeout=None):
        raise error

    monkeypatch.setattr(telegram, "urlopen", fail)
    services.collect()
    with caplog.at_level(logging.DEBUG):
        services.flush(at(D(2026, 11, 20), 12))
        with pytest.raises(telegram.TelegramError) as raised:
            telegram.send("x")
    assert TOKEN not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__
    assert TOKEN not in caplog.text
    assert TOKEN not in Notification.objects.get().last_error


def test_token_nunca_aparece_na_tarefa(setup_bot, bill, monkeypatch, caplog):
    def explode():
        raise telegram.TelegramError(telegram.scrub(f"bot{TOKEN}"))

    job = jobs.Job("teste_telegram", "Teste", jobs.daily_due, explode)
    with caplog.at_level(logging.DEBUG):
        jobs.run_due(at(D(2026, 11, 20), 12), jobs=[job])
    assert TOKEN not in JobRun.objects.get(job_name="teste_telegram").message
    assert TOKEN not in caplog.text


def test_tarefa_esta_no_agendador_e_roda_as_oito(setup_bot, bill):
    job = next(j for j in jobs.JOBS if j.name == "telegram_alerts")
    assert job.due(at(D(2026, 11, 20), 9)).hour == 8
    assert job.due(at(D(2026, 11, 20), 7)).date() == D(2026, 11, 19)


def test_volta_do_agendador_envia_a_fila(setup_bot, bill, net):
    services.collect()
    with travel_to(D(2026, 11, 20)):
        jobs.tick(at(D(2026, 11, 20), 12), jobs_to_run=[])
    assert len(net) == 1


def test_falha_de_backup_avisa(setup_bot):
    JobRun.objects.create(
        job_name="daily_backup",
        scheduled_for=timezone.now(),
        status="failed",
        message="verificação de integridade",
    )
    services.collect()
    assert "Backup de hoje falhou: verificação de integridade" in texts()


def test_sem_backup_recente_avisa_uma_vez_por_dia(setup_bot):
    BackupRecord.objects.all().delete()
    services.collect()
    services.collect()
    assert texts() == ["Nenhum backup bom nas últimas 36 horas."]


def test_bloqueio_de_login_entra_na_fila(setup_bot, client, user):
    for _ in range(5):
        response = client.post("/acesso/entrar/", {"password": "tentativa-x"})
    assert response.status_code in (200, 403)
    assert any("bloqueado" in t.lower() for t in texts())
    item = Notification.objects.get(kind="security")
    assert "tentativa-x" not in item.summary


def test_problema_no_aviso_nao_atrapalha_o_login(client, user, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("banco ocupado")

    monkeypatch.setattr(telegram, "configured", boom)
    services.enqueue_safely("security", "x", "k")
    user_login_failed.send(sender=None, credentials={}, request=None)
    assert client.post("/acesso/entrar/", {"password": PASSWORD}).status_code == 302


def test_aparelho_novo_avisa(setup_bot, user):
    device, _ = devices.issue(user, name="Celular", pin="123456")
    assert "Celular" in Notification.objects.get(kind="security").summary


def form_data(**extra):
    return {
        "token": TOKEN,
        "chat_id": "777",
        "days_before": 3,
        "quiet_start": 22,
        "quiet_end": 7,
        "password": PASSWORD,
        **extra,
    }


def test_tela_exige_a_senha(web):
    html = web.post("/ajustes/avisos/", form_data(password="errada")).content.decode()  # noqa: S106
    assert "Senha incorreta" in html
    assert not secrets.has(secrets.TELEGRAM_TOKEN)
    assert TOKEN not in html


def test_token_fica_no_cofre_e_fora_do_banco(web):
    response = web.post("/ajustes/avisos/", form_data(), follow=True)
    html = response.content.decode()
    assert secrets.get(secrets.TELEGRAM_TOKEN) == TOKEN
    assert TOKEN not in html and "Token guardado no cofre" in html
    assert not any(TOKEN in str(s.value) for s in Setting.objects.all())
    from apps.ledger.models import AuditLog

    assert not any(TOKEN in str(a.after_json) for a in AuditLog.objects.all())


def test_token_em_branco_mantem_o_atual(web, setup_bot):
    web.post("/ajustes/avisos/", form_data(token="", days_before=5))
    assert secrets.get(secrets.TELEGRAM_TOKEN) == TOKEN
    assert services.days_before() == 5


def test_token_mal_formado_recusado(web):
    html = web.post("/ajustes/avisos/", form_data(token="abc")).content.decode()  # noqa: S106
    assert "formato" in html and not secrets.has(secrets.TELEGRAM_TOKEN)


def test_mensagem_de_teste(web, setup_bot, net):
    html = web.post("/ajustes/avisos/teste/", follow=True).content.decode()
    assert "Mensagem de teste enviada" in html and len(net) == 1


def test_mensagem_de_teste_com_erro_explica(web, setup_bot, monkeypatch):
    def fail(request, timeout=None):
        raise HTTPError("u", 401, "x", {}, None)

    monkeypatch.setattr(telegram, "urlopen", fail)
    html = web.post("/ajustes/avisos/teste/", follow=True).content.decode()
    assert "recusou o token" in html and TOKEN not in html
