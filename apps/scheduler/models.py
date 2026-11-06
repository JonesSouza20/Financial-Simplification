"""Execuções de tarefas agendadas (database-design.md §10; ADR-018)."""

from django.db import models


class JobRun(models.Model):
    job_name = models.CharField(max_length=40)
    scheduled_for = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default="running")  # running, ok, failed
    message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        db_table = "job_run"
        ordering = ["-scheduled_for", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["job_name", "scheduled_for"], name="job_run_once")
        ]

    def __str__(self) -> str:
        return f"{self.job_name} {self.scheduled_for:%d/%m %H:%M} {self.status}"
