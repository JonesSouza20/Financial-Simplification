"""Feriados (database-design.md §9.2; RN-092). Tabela editável pelo usuário."""

from django.db import models


class HolidayScope(models.TextChoices):
    NATIONAL = "national", "Nacional"
    STATE = "state", "Estadual"
    MUNICIPAL = "municipal", "Municipal"
    CARNIVAL = "carnival", "Carnaval"
    CUSTOM = "custom", "Personalizado"


class Holiday(models.Model):
    date = models.DateField(primary_key=True)
    name = models.CharField(max_length=80)
    scope = models.CharField(max_length=12, choices=HolidayScope.choices)
    affects_salary = models.BooleanField(default=True)
    affects_banking = models.BooleanField(default=True)

    class Meta:
        db_table = "holiday"
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.date:%d/%m/%Y} {self.name}"
