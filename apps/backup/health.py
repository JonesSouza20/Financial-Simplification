"""Saúde do sistema (F-001 §13; architecture.md §11; security-plan.md §5, §12)."""

from __future__ import annotations

import datetime
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
        issues.append(f"Último backup com problema: {last.message or 'verificação falhou'}.")
    if last_ok and last_ok.cloud_ok is None and core.cloud_dir() is not None:
        issues.append("O último backup bom não foi copiado para a nuvem.")
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
        "version": settings.FINANCAS_VERSION,
        "cloud": core.cloud_dir(),
        "local": core.local_dir(),
    }


def level(issues: list[str]) -> str:
    """Ponto de saúde no topo: verde, amarelo ou vermelho (ui-ux-specification.md §8.1)."""
    if not issues:
        return "ok"
    serious = ("integridade", "falhou", "Nenhum backup", "não configurada: nenhum")
    return "bad" if any(s in i for i in issues for s in serious) else "warn"
