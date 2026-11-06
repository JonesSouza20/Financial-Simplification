"""Contas contábeis de sistema: Patrimônio:Abertura e Patrimônio:Ajustes (business-rules.md §2)."""

from django.db import migrations

SYSTEM_ACCOUNTS = [
    ("equity:opening", "Patrimônio: Abertura"),
    ("equity:adjustments", "Patrimônio: Ajustes de conciliação"),
]


def create(apps, schema_editor):
    LedgerAccount = apps.get_model("ledger", "LedgerAccount")
    for code, name in SYSTEM_ACCOUNTS:
        LedgerAccount.objects.get_or_create(
            code=code,
            defaults={"kind": "equity", "name": name, "is_system": True},
        )


class Migration(migrations.Migration):
    dependencies = [("ledger", "0002_triggers")]

    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
