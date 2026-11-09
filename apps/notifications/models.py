"""Avisos enviados (database-design.md §9.4). O token nunca fica aqui: está no cofre (ADR-020)."""

from django.db import models


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Na fila"
    SENT = "sent", "Enviado"
    FAILED = "failed", "Não enviado"


class NotificationKind(models.TextChoices):
    DUE = "due", "Vencimento"
    OVERDUE = "overdue", "Atraso"
    BACKUP = "backup", "Backup"
    SECURITY = "security", "Segurança"


class Notification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=12, choices=NotificationKind.choices)
    channel = models.CharField(max_length=12, default="telegram")
    summary = models.CharField(max_length=300)
    # Mesma chave, mesmo aviso: a restrição impede repetir mesmo com duas execuções.
    dedup_key = models.CharField(max_length=120, unique=True)
    status = models.CharField(
        max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.PENDING
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    next_try_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.summary
