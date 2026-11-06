"""Confiança de aparelho e PIN (ADR-019, ADR-035; security-plan.md §3.4).

O PIN só reabre a sessão de um aparelho já confiável. A confiança nasce e é renovada
apenas por login com senha. Cinco erros de PIN revogam o aparelho.
"""

from __future__ import annotations

import datetime
import hashlib
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.ledger import audit

from .models import TrustedDevice

DEVICE_COOKIE = "fin_device"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def trivial_pin(pin: str) -> bool:
    """Recusa PIN repetido (000000) ou sequencial (123456, 654321)."""
    if len(set(pin)) == 1:
        return True
    digits = [int(c) for c in pin]
    steps = {b - a for a, b in zip(digits, digits[1:], strict=False)}
    return steps in ({1}, {-1})


def trust_days() -> datetime.timedelta:
    return datetime.timedelta(days=settings.FINANCAS_DEVICE_TRUST_DAYS)


@transaction.atomic
def issue(user, *, name: str, pin: str, user_agent: str = "") -> tuple[TrustedDevice, str]:
    """Cria a confiança do aparelho. Devolve o token em claro, só para gravar no cookie."""
    token = secrets.token_urlsafe(32)  # 256 bits
    device = TrustedDevice.objects.create(
        user=user,
        name=name.strip()[:60] or "Aparelho",
        token_hash=hash_token(token),
        pin_hash=make_password(pin),
        expires_at=timezone.now() + trust_days(),
        user_agent_summary=user_agent[:120],
    )
    audit.record_event("device_trusted", "trusted_device", device.pk, after={"name": device.name})
    return device, token


def find(request) -> TrustedDevice | None:
    token = request.COOKIES.get(DEVICE_COOKIE)
    if not token:
        return None
    device = TrustedDevice.objects.filter(token_hash=hash_token(token)).first()
    if device is None or device.revoked_at or device.expires_at <= timezone.now():
        return None
    return device


def renew(device: TrustedDevice) -> None:
    """Renova a validade. Chamado só depois de login com senha (ADR-035)."""
    TrustedDevice.objects.filter(pk=device.pk).update(expires_at=timezone.now() + trust_days())


@transaction.atomic
def verify_pin(device: TrustedDevice, pin: str) -> bool:
    device = TrustedDevice.objects.select_for_update().get(pk=device.pk)
    if device.revoked_at:
        return False
    if check_password(pin, device.pin_hash):
        device.failed_pin_attempts = 0
        device.last_used_at = timezone.now()
        device.save(update_fields=["failed_pin_attempts", "last_used_at"])
        audit.record_event("pin_unlock", "trusted_device", device.pk)
        return True
    device.failed_pin_attempts += 1
    device.save(update_fields=["failed_pin_attempts"])
    audit.record_event(
        "pin_failed", "trusted_device", device.pk, after={"failures": device.failed_pin_attempts}
    )
    if device.failed_pin_attempts >= settings.FINANCAS_PIN_MAX_FAILURES:
        revoke(device, reason="5 erros de PIN")
    return False


def revoke(device: TrustedDevice, *, reason: str) -> None:
    TrustedDevice.objects.filter(pk=device.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_reason=reason[:120]
    )
    audit.record_event("device_revoked", "trusted_device", device.pk, reason=reason)


def revoke_all(user, *, reason: str) -> int:
    devices = list(TrustedDevice.objects.filter(user=user, revoked_at__isnull=True))
    for device in devices:
        revoke(device, reason=reason)
    return len(devices)


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        DEVICE_COOKIE,
        token,
        max_age=int(trust_days().total_seconds()),
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="Strict",
    )
