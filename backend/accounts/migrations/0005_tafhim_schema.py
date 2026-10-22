from pathlib import Path

from django.db import migrations
import sqlparse


def create_tafhim_schema(apps, schema_editor):
    schema_path = Path(__file__).resolve().parents[2] / "database" / "tafhim_schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    with schema_editor.connection.cursor() as cursor:
        for statement in sqlparse.split(schema_sql):
            nonempty_lines = [line.lstrip() for line in statement.splitlines() if line.strip()]
            if nonempty_lines and not all(line.startswith("--") for line in nonempty_lines):
                cursor.execute(statement)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0004_note"),
    ]

    operations = [
        migrations.RunPython(create_tafhim_schema),
    ]
