"""Registro de logins e bloqueios na auditoria (RN-191). Nunca grava senha ou PIN."""

from axes.signals import user_locked_out
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from apps.ledger import audit


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    method = request.session.get("auth_method", "password") if request else "password"
    audit.record_event("login", "auth_user", user.pk, after={"method": method})


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    audit.record_event("login_failed", "auth_user", 0)


@receiver(user_locked_out)
def on_locked_out(sender, request=None, **kwargs):
    """Registra um bloqueio novo. Tentativas durante o mesmo bloqueio não contam de novo."""
    from django.utils import timezone

    from apps.ledger.models import AuditLog

    from .lockout import cooloff

    last = AuditLog.objects.filter(action="lockout").order_by("-at").first()
    if last and timezone.now() - last.at < cooloff():
        return
    audit.record_event("lockout", "auth_user", 0)
    from apps.notifications.services import enqueue_safely

    now = timezone.localtime()
    enqueue_safely(
        "security",
        f"Login bloqueado por tentativas erradas às {now:%H:%M}.",
        f"lockout:{now.isoformat(timespec='minutes')}",
    )
