"""Saúde do sistema (F-001 §13; architecture.md §11; security-plan.md §5, §12)."""

from __future__ import annotations

import datetime
import json
import shutil
import subprocess  # noqa: S404 - comando fixo, sem dados do usuário
import sys
import time

from django.conf import settings
from django.utils import timezone

from apps.ledger.invariants import check_all
from apps.scheduler.jobs import last_runs

from . import core, secrets
from .models import BackupRecord, RestoreTest

_encryption_cache: dict = {}
_funnel_cache: dict = {}

BITLOCKER_ON = {1, 3, 5, 6}


def disk_encryption() -> str:
    """Criptografia do dispositivo no disco do banco (ADR-022). Sem administrador."""
    cached = _encryption_cache.get("value")
    if cached and time.time() - _encryption_cache["at"] < 3600:
        return cached
    if sys.platform != "win32":
        return "não verificado (fora do Windows)"
    drive = str(core.db_path().resolve().drive or "C:")
    command = (
        "(New-Object -ComObject Shell.Application).NameSpace('" + drive + "')"
        ".Self.ExtendedProperty('System.Volume.BitLockerProtection')"
    )
    try:
        out = subprocess.run(  # noqa: S603
            ["powershell", "-NoProfile", "-Command", command],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        ).stdout.strip()
        code = int(out) if out.isdigit() else None
    except (OSError, subprocess.SubprocessError):
        code = None
    if code in BITLOCKER_ON:
        value = "ativa"
    elif code == 2:
        value = "desligada"
    else:
        value = "não disponível neste PC"
    _encryption_cache.update(value=value, at=time.time())
    return value


TAILSCALE_EXE = r"C:\Program Files\Tailscale\tailscale.exe"


def funnel() -> str:
    """Funnel do Tailscale (publicação na internet) deve ficar sempre desligado
    (security-plan.md §4). Lê a configuração do Serve; não altera nada."""
    cached = _funnel_cache.get("value")
    if cached and time.time() - _funnel_cache["at"] < 3600:
        return cached
    exe = shutil.which("tailscale") or (TAILSCALE_EXE if sys.platform == "win32" else None)
    value = "não verificado"
    if exe:
        try:
            done = subprocess.run(  # noqa: S603
                [exe, "serve", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            config = json.loads(done.stdout) if done.returncode == 0 else None
            # Só diz "desligado" com resposta válida; qualquer dúvida fica "não verificado".
            # Formato conferido na versão instalada (security-plan.md, nota inicial).
            if isinstance(config, dict) and isinstance(config.get("AllowFunnel", {}), dict):
                value = "ligado" if any(config.get("AllowFunnel", {}).values()) else "desligado"
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    _funnel_cache.update(value=value, at=time.time())
    return value


def report() -> dict:
    now = timezone.now()
    last = BackupRecord.objects.first()
    last_ok = BackupRecord.objects.filter(checks_passed=True, local_ok=True).first()
    test = RestoreTest.objects.exclude(kind="restore").first()
    usage = shutil.disk_usage(settings.DATA_DIR)
    issues = []
    if not secrets.has(secrets.BACKUP_PASSPHRASE):
        issues.append("Senha de backup não configurada: nenhum backup está sendo feito.")
    if core.cloud_dir() is None:
        issues.append("Pasta da nuvem não configurada: o backup fica só neste PC.")
    if last_ok is None or now - last_ok.created_at > datetime.timedelta(hours=36):
        issues.append("Nenhum backup bom nas últimas 36 horas.")
    if last is not None and not last.ok:
        problem = (last.message or "verificação falhou").rstrip(".")
        issues.append(f"Último backup com problema: {problem}.")
    if last_ok and last_ok.cloud_ok is None and core.cloud_dir() is not None:
        issues.append("O último backup bom não foi copiado para a nuvem.")
    last_cloud = BackupRecord.objects.filter(cloud_ok=True).first()
    if core.cloud_dir() is not None and (
        last_cloud is None or now - last_cloud.created_at > datetime.timedelta(hours=72)
    ):
        issues.append("Cópia na pasta da nuvem com mais de 72 horas (ou nunca feita).")
    if test is None or now - test.at > datetime.timedelta(days=40):
        issues.append("Teste de restauração com mais de 40 dias (ou nunca feito).")
    elif not test.passed:
        issues.append("O último teste de restauração falhou.")
    violations = check_all()
    if violations:
        issues.append(f"{len(violations)} problema(s) de integridade nos dados.")
    if settings.DEBUG:
        issues.append("Modo de depuração ligado: não use com dados reais.")
    encryption = disk_encryption()
    if encryption != "ativa":
        issues.append(f"Criptografia do disco: {encryption} (risco aceito na ADR-022).")
    exposure = funnel()
    if exposure == "ligado":
        issues.append("Funnel do Tailscale ligado: o sistema está exposto na internet.")
    elif exposure != "desligado":
        issues.append(
            "Não foi possível conferir o Funnel do Tailscale; confira à mão com "
            "'tailscale funnel status'."
        )
    if usage.free < 1024**3:
        issues.append("Menos de 1 GB livre no disco.")
    return {
        "issues": issues,
        "last": last,
        "last_ok": last_ok,
        "test": test,
        "violations": violations,
        "runs": last_runs(),
        "free_gb": round(usage.free / 1024**3, 1),
        "encryption": encryption,
        "funnel": exposure,
        "last_cloud": last_cloud,
        "version": settings.FINANCAS_VERSION,
        "cloud": core.cloud_dir(),
        "local": core.local_dir(),
    }


def level(issues: list[str]) -> str:
    """Ponto de saúde no topo: verde, amarelo ou vermelho (ui-ux-specification.md §8.1)."""
    if not issues:
        return "ok"
    serious = (
        "integridade",
        "falhou",
        "Nenhum backup",
        "não configurada: nenhum",
        "Funnel do Tailscale ligado",
    )
    return "bad" if any(s in i for i in issues for s in serious) else "warn"
