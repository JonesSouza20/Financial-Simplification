"""Configurações simples em chave e valor (database-design.md §9.3)."""

from django.db import models


class Setting(models.Model):
    key = models.CharField(max_length=60, primary_key=True)
    value = models.JSONField(null=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "setting"

    def __str__(self) -> str:
        return self.key


def get(key: str, default=None):
    row = Setting.objects.filter(key=key).first()
    return row.value if row else default


def put(key: str, value) -> None:
    Setting.objects.update_or_create(key=key, defaults={"value": value})
