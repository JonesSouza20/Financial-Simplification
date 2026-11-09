from django.db import migrations

from apps.payables import db_triggers


def install(apps, schema_editor):
    db_triggers.install(schema_editor.connection)


def uninstall(apps, schema_editor):
    db_triggers.uninstall(schema_editor.connection)


class Migration(migrations.Migration):
    dependencies = [("payables", "0001_initial")]

    operations = [migrations.RunPython(install, uninstall)]
