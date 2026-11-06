"""Aparelhos confiáveis (database-design.md §10; security-plan.md §3.4)."""

from django.conf import settings
from django.db import models


class TrustedDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256 do token; nunca o token
    pin_hash = models.CharField(max_length=200)  # Argon2id
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=120, blank=True, default="")
    user_agent_summary = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "trusted_device"

    def __str__(self) -> str:
        return self.name
