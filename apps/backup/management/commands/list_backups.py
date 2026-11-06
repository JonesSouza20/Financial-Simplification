"""Lista os backups disponíveis (pasta local e nuvem), do mais novo para o mais antigo."""

from django.core.management.base import BaseCommand

from apps.backup.core import available


class Command(BaseCommand):
    help = "Lista os backups disponíveis."

    def handle(self, *args, **options):
        items = available()
        for entry in items:
            self.stdout.write(f"{entry.name}  ({entry.manifest['trigger']}, {entry.path.parent})")
        if not items:
            self.stdout.write("Nenhum backup encontrado.")
