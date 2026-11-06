"""Confere as invariantes do Ledger (business-rules.md §21). Sai com erro se houver problema."""

from django.core.management.base import BaseCommand, CommandError

from apps.ledger.invariants import check_all


class Command(BaseCommand):
    help = "Verifica a integridade dos dados financeiros."

    def handle(self, *args, **options):
        violations = check_all()
        for v in violations:
            self.stdout.write(f"{v.code}: {v.detail}")
        if violations:
            raise CommandError(f"{len(violations)} problema(s) de integridade.")
        self.stdout.write("Integridade OK.")
