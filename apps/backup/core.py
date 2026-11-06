"""Backup, retenção e restauração (ADR-021; architecture.md §10; security-plan.md §7).

Fluxo do backup:
1. cópia online do SQLite (API de backup, com o sistema funcionando);
2. verificação da cópia (integridade e invariantes);
3. compressão e criptografia `age` com a senha de backup;
4. gravação na pasta local e na pasta da nuvem, com conferência do SHA-256;
5. retenção (7 diários, 4 semanais, 12 mensais; pré-atualização por 90 dias).
"""

from __future__ import annotations

import datetime
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pyrage
from django.conf import settings
from django.db import connection, connections
from django.utils import timezone

from apps.ledger.errors import LedgerError

from . import secrets, verify
from .models import BackupRecord, RestoreTest

PREFIX = "financas-"
KEEP_ALWAYS_DAYS_TRIGGERS = ("pre_update", "pre_migration", "pre_restore", "manual")


class BackupError(LedgerError):
    """Falha de backup ou restauração, com mensagem para o usuário."""


# Caminhos ----------------------------------------------------------------------------


def db_path() -> Path:
    return Path(connection.settings_dict["NAME"])


def local_dir() -> Path:
    path = Path(settings.FINANCAS_BACKUP_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cloud_dir() -> Path | None:
    from apps.ui import models as prefs

    value = prefs.get("backup_cloud_dir")
    return Path(value) if value else None


def set_cloud_dir(value: str) -> Path:
    from apps.ui import models as prefs

    path = Path(value).expanduser()
    if not path.is_dir():
        raise BackupError("Pasta da nuvem não encontrada. Confira o caminho.")
    probe = path / f".financas-teste-{uuid.uuid4().hex[:6]}"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise BackupError("Sem permissão para gravar na pasta da nuvem.") from exc
    prefs.put("backup_cloud_dir", str(path))
    return path


@contextmanager
def workdir():
    """Pasta temporária dentro da pasta de dados (protegida), apagada no fim, mesmo em erro."""
    base = Path(settings.DATA_DIR) / "tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Peças ---------------------------------------------------------------------------------


def snapshot(source: Path, target: Path) -> None:
    """Cópia consistente com o banco em uso (API de backup online do SQLite)."""
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def passphrase_or_error(passphrase: str | None = None) -> str:
    value = passphrase or secrets.get(secrets.BACKUP_PASSPHRASE)
    if not value:
        raise BackupError("Senha de backup não configurada. Defina em Backup.")
    return value


def encrypt(plain: bytes, passphrase: str) -> bytes:
    return pyrage.passphrase.encrypt(gzip.compress(plain, compresslevel=6), passphrase)


def decrypt(blob: bytes, passphrase: str) -> bytes:
    try:
        return gzip.decompress(pyrage.passphrase.decrypt(blob, passphrase))
    except pyrage.DecryptError as exc:
        raise BackupError("Senha de backup incorreta ou arquivo danificado.") from exc
    except (OSError, EOFError) as exc:
        raise BackupError("Arquivo de backup danificado.") from exc


# Backup --------------------------------------------------------------------------------


def _write_verified(directory: Path, name: str, blob: bytes, manifest: dict) -> bool:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.db.age"
    target.write_bytes(blob)
    (directory / f"{name}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return sha256_bytes(target.read_bytes()) == manifest["encrypted_sha256"]


def create_backup(
    trigger: str = "daily", *, passphrase: str | None = None, now: datetime.datetime | None = None
) -> BackupRecord:
    """Gera um backup verificado. Em falha, grava o registro com a mensagem e levanta erro."""
    now = now or timezone.localtime()
    record = BackupRecord(trigger=trigger, app_version=settings.FINANCAS_VERSION)
    try:
        key = passphrase_or_error(passphrase)
        with workdir() as tmp:
            copy = tmp / "copia.db"
            snapshot(db_path(), copy)
            found = verify.problems(copy)
            if found:
                raise BackupError("Verificação da cópia falhou: " + "; ".join(found))
            plain = copy.read_bytes()
            blob = encrypt(plain, key)
            name = f"{PREFIX}{now:%Y%m%d-%H%M%S}-{trigger}"
            manifest = {
                "format": 1,
                "file": f"{name}.db.age",
                "created_at": now.isoformat(),
                "trigger": trigger,
                "app_version": settings.FINANCAS_VERSION,
                "schema": verify.schema(copy),
                "counts": verify.counts(copy),
                "plain_sha256": sha256_bytes(plain),
                "encrypted_sha256": sha256_bytes(blob),
                "size_bytes": len(blob),
            }
        record.checks_passed = True
        record.file_name = manifest["file"]
        record.sha256 = manifest["encrypted_sha256"]
        record.size_bytes = manifest["size_bytes"]
        record.schema_version = manifest["schema"]
        record.local_ok = _write_verified(local_dir(), name, blob, manifest)
        cloud = cloud_dir()
        if cloud is not None:
            try:
                record.cloud_ok = _write_verified(cloud, name, blob, manifest)
            except OSError:
                record.cloud_ok = False
        if not record.local_ok:
            raise BackupError("O arquivo gravado na pasta local não confere com o original.")
        if record.cloud_ok is False:
            record.message = "Cópia na nuvem falhou; a cópia local está boa."
        for directory in filter(None, [local_dir(), cloud]):
            apply_retention(directory, now)
    except BackupError as exc:
        record.message = str(exc)[:300]
        record.save()
        raise
    record.save()
    return record


# Retenção ------------------------------------------------------------------------------


@dataclass
class Entry:
    manifest: dict
    path: Path

    @property
    def created(self) -> datetime.datetime:
        return datetime.datetime.fromisoformat(self.manifest["created_at"])

    @property
    def name(self) -> str:
        return self.manifest["file"]


def entries(directory: Path) -> list[Entry]:
    """Backups de uma pasta, do mais novo para o mais antigo (pelos manifestos)."""
    found = []
    if not directory or not directory.is_dir():
        return found
    for manifest_path in directory.glob(f"{PREFIX}*.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        blob = directory / manifest.get("file", "")
        if blob.is_file():
            found.append(Entry(manifest, blob))
    return sorted(found, key=lambda e: e.created, reverse=True)


def keep_set(items: list[Entry], now: datetime.datetime) -> set[str]:
    """Nomes a manter (security-plan.md §7.1)."""
    rules = settings.FINANCAS_RETENTION
    keep: set[str] = set()
    regular = [e for e in items if e.manifest["trigger"] not in KEEP_ALWAYS_DAYS_TRIGGERS]
    for e in items:
        if e.manifest["trigger"] in KEEP_ALWAYS_DAYS_TRIGGERS and (
            now - e.created <= datetime.timedelta(days=rules["pre_update_days"])
        ):
            keep.add(e.name)

    def newest_per(key, limit):
        seen = []
        for e in regular:  # já do mais novo para o mais antigo
            k = key(e.created)
            if k not in seen:
                seen.append(k)
                if len(seen) > limit:
                    break
                keep.add(e.name)

    newest_per(lambda d: d.date(), rules["daily"])
    newest_per(lambda d: d.isocalendar()[:2], rules["weekly"])
    newest_per(lambda d: (d.year, d.month), rules["monthly"])
    return keep


def apply_retention(directory: Path, now: datetime.datetime | None = None) -> list[str]:
    now = now or timezone.localtime()
    items = entries(directory)
    keep = keep_set(items, now)
    removed = []
    for e in items:
        if e.name not in keep:
            e.path.unlink(missing_ok=True)
            e.path.with_name(e.path.name.replace(".db.age", ".json")).unlink(missing_ok=True)
            removed.append(e.name)
    return removed


def available() -> list[Entry]:
    """Backups da pasta local e da nuvem, sem repetir nomes (local primeiro)."""
    seen, result = set(), []
    for directory in filter(None, [local_dir(), cloud_dir()]):
        for e in entries(directory):
            if e.name not in seen:
                seen.add(e.name)
                result.append(e)
    return sorted(result, key=lambda e: e.created, reverse=True)


def find(name: str) -> Entry:
    for e in available():
        if e.name == name:
            return e
    raise BackupError("Backup não encontrado.")


# Restauração ---------------------------------------------------------------------------


def _materialize(entry: Entry, passphrase: str, target: Path) -> dict:
    """Descriptografa para `target` e verifica tudo. Devolve detalhes; levanta em falha."""
    blob = entry.path.read_bytes()
    if sha256_bytes(blob) != entry.manifest["encrypted_sha256"]:
        raise BackupError("O arquivo de backup não confere com o manifesto (SHA-256).")
    plain = decrypt(blob, passphrase)
    if sha256_bytes(plain) != entry.manifest["plain_sha256"]:
        raise BackupError("O conteúdo descriptografado não confere com o manifesto.")
    target.write_bytes(plain)
    found = verify.problems(target)
    if found:
        raise BackupError("Verificação falhou: " + "; ".join(found))
    counts = verify.counts(target)
    if counts != entry.manifest["counts"]:
        raise BackupError("As contagens não conferem com o manifesto.")
    return {
        "counts": counts,
        "created_at": entry.manifest["created_at"],
        "schema": entry.manifest["schema"],
    }


def test_restore(entry: Entry, *, passphrase: str | None = None, kind: str = "manual"):
    """Restaura num arquivo temporário e verifica, sem tocar no banco em uso."""
    try:
        key = passphrase_or_error(passphrase)
        with workdir() as tmp:
            details = _materialize(entry, key, tmp / "restaurado.db")
        test = RestoreTest.objects.create(
            file_name=entry.name, kind=kind, passed=True, details_json=details
        )
    except BackupError as exc:
        RestoreTest.objects.create(
            file_name=entry.name, kind=kind, passed=False, details_json={"error": str(exc)}
        )
        raise
    return test


def restore_into(target: Path, entry: Entry, passphrase: str) -> dict:
    """Copia o backup verificado para dentro de `target` pela API de backup do SQLite."""
    with workdir() as tmp:
        restored = tmp / "restaurado.db"
        details = _materialize(entry, passphrase, restored)
        snapshot(restored, target)
    return details


def restore_live(entry: Entry, *, passphrase: str) -> dict:
    """Restaura sobre o banco em uso (F-100). Faz backup do estado atual antes."""
    create_backup("pre_restore", passphrase=passphrase)
    connections.close_all()
    details = restore_into(db_path(), entry, passphrase)
    connections.close_all()
    RestoreTest.objects.create(
        file_name=entry.name, kind="restore", passed=True, details_json=details
    )
    from apps.ledger import audit

    audit.record_event("restore", "backup", 0, after={"file": entry.name})
    return details


def monthly_restore_test() -> RestoreTest:
    """Teste automático mensal com o backup local mais recente (security-plan.md §7.4)."""
    items = entries(local_dir())
    if not items:
        raise BackupError("Nenhum backup local para testar.")
    return test_restore(items[0], kind="auto")
