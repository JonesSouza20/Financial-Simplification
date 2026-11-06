"""Restaura um backup pelo terminal (ops/restore.ps1 e ops/install.ps1 -RestoreFrom, com o
serviço parado).

Primeiro restaura numa cópia temporária, verifica e mostra o resumo; só depois pergunta se
substitui (security-plan.md §7.2). Com --test, para no resumo (§7.5).
"""

import datetime
import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.backup import core
from apps.money import Money


class Command(BaseCommand):
    help = "Restaura (ou testa) um backup. A senha de backup é pedida no terminal."

    def add_arguments(self, parser):
        parser.add_argument(
            "name", help="Nome do arquivo .db.age (veja list_backups) ou caminho completo."
        )
        parser.add_argument("--test", action="store_true", help="Só testar, sem substituir.")

    def handle(self, *args, name, test=False, **options):
        try:
            entry = core.find(name)
            passphrase = getpass.getpass("Senha de backup: ")
            result = core.test_restore(entry, passphrase=passphrase, kind="manual")
            self._summary(result.details_json)
            if test:
                self.stdout.write("Teste OK. Nada foi substituído.")
                return
            answer = input("Os dados atuais serão substituídos. Digite RESTAURAR para seguir: ")
            if answer.strip() != "RESTAURAR":
                raise CommandError("Restauração cancelada. Nada foi alterado.")
            details = core.restore_live(entry, passphrase=passphrase)
        except core.BackupError as exc:
            raise CommandError(f"Nada foi substituído: {exc}") from exc
        self.stdout.write(
            f"Restaurado de {entry.name} ({details['counts']['ledger_transaction']} "
            "transações). Aparelhos confiáveis e sessões vieram do backup."
        )

    def _summary(self, details):
        created = datetime.datetime.fromisoformat(details["created_at"])
        counts, summary = details["counts"], details["summary"]
        self.stdout.write(
            f"Backup de {created:%d/%m/%Y %H:%M}: {counts['ledger_transaction']} transações, "
            f"{counts['financial_account']} contas."
        )
        if summary["last"]:
            day = datetime.date.fromisoformat(summary["last"]["date"])
            description = summary["last"]["description"]
            self.stdout.write(f"Último lançamento: {day:%d/%m/%Y} · {description}")
        for account in summary["accounts"]:
            self.stdout.write(f"  {account['name']}: {Money(account['cents']).format_brl()}")
