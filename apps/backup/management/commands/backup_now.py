"""Faz um backup verificado agora (usado antes de atualizar e de migrar)."""

from django.core.management.base import BaseCommand, CommandError

from apps.backup.core import BackupError, create_backup

TRIGGERS = ("manual", "daily", "pre_update", "pre_migration")


class Command(BaseCommand):
    help = "Gera um backup criptografado e verificado (local e nuvem)."

    def add_arguments(self, parser):
        parser.add_argument("--trigger", choices=TRIGGERS, default="manual")

    def handle(self, *args, trigger, **options):
        try:
            record = create_backup(trigger)
        except BackupError as exc:
            raise CommandError(f"Backup falhou: {exc}") from exc
        cloud = {None: "nuvem não configurada", True: "nuvem ok", False: "nuvem FALHOU"}
        self.stdout.write(f"Backup {record.file_name}: local ok, {cloud[record.cloud_ok]}.")
