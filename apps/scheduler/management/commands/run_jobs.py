"""Executa as tarefas devidas uma vez (plano B pelo Agendador de Tarefas do Windows)."""

from django.core.management.base import BaseCommand

from apps.scheduler.jobs import run_due


class Command(BaseCommand):
    help = "Executa backup e teste de restauração que estiverem devidos."

    def handle(self, *args, **options):
        runs = run_due()
        for run in runs:
            self.stdout.write(f"{run.job_name}: {run.status} {run.message}")
        if not runs:
            self.stdout.write("Nada devido.")
