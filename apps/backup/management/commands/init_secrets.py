"""Cria a chave da aplicação no cofre do Windows e, se pedido, a senha de backup (ADR-020)."""

import getpass
import secrets as pysecrets

from django.core.management.base import BaseCommand, CommandError

from apps.backup import secrets
from apps.ledger.errors import LedgerError


class Command(BaseCommand):
    help = "Prepara os segredos no Cofre de Credenciais do Windows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-passphrase", action="store_true", help="Pergunta e grava a senha de backup."
        )

    def handle(self, *args, backup_passphrase=False, **options):
        if secrets.has(secrets.SECRET_KEY):
            self.stdout.write("Chave da aplicação já existe no cofre.")
        else:
            secrets.put(secrets.SECRET_KEY, pysecrets.token_urlsafe(64))
            self.stdout.write("Chave da aplicação criada no cofre do Windows.")
        if backup_passphrase:
            first = getpass.getpass("Senha de backup (16+ caracteres): ")
            second = getpass.getpass("Repita a senha de backup: ")
            if first != second:
                raise CommandError("As senhas não são iguais. Nada foi gravado.")
            try:
                secrets.validate_passphrase(first)
            except LedgerError as exc:
                raise CommandError(str(exc)) from exc
            secrets.put(secrets.BACKUP_PASSPHRASE, first)
            self.stdout.write("Senha de backup gravada. Guarde-a também fora do sistema.")
