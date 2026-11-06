"""Registros de backup e de testes de restauração (database-design.md §10)."""

from django.db import models


class BackupRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    trigger = models.CharField(
        max_length=16
    )  # daily, pre_update, pre_migration, pre_restore, manual
    file_name = models.CharField(max_length=120, blank=True, default="")
    sha256 = models.CharField(max_length=64, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    schema_version = models.CharField(max_length=64, blank=True, default="")
    app_version = models.CharField(max_length=20, blank=True, default="")
    checks_passed = models.BooleanField(default=False)
    local_ok = models.BooleanField(default=False)
    cloud_ok = models.BooleanField(null=True)  # None = pasta da nuvem não configurada
    message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "backup_record"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.file_name or f"backup {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def ok(self) -> bool:
        return self.checks_passed and self.local_ok and self.cloud_ok is not False


class RestoreTest(models.Model):
    at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8)  # auto, manual, restore
    passed = models.BooleanField(default=False)
    details_json = models.JSONField(default=dict)

    class Meta:
        db_table = "restore_test"
        ordering = ["-at", "-id"]

    def __str__(self) -> str:
        return f"{self.kind} {self.file_name}"
