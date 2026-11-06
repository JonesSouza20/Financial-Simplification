"""Instala os gatilhos de integridade (database-design.md §11)."""

from django.db import migrations

from apps.ledger.db_triggers import install_sql, uninstall_sql


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]

    operations = [migrations.RunSQL(sql=install_sql(), reverse_sql=uninstall_sql())]
