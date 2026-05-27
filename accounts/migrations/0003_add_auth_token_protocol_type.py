from django.db import migrations, models


def add_columns_if_missing(apps, schema_editor):
    """Idempotent column additions for partially-migrated databases."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'accounts_sshaccount'"
        )
        existing = {row[0] for row in cursor.fetchall()}

    with connection.cursor() as cursor:
        if "auth_token" not in existing:
            cursor.execute(
                "ALTER TABLE accounts_sshaccount ADD COLUMN auth_token uuid NULL"
            )
        if "protocol_type" not in existing:
            cursor.execute(
                "ALTER TABLE accounts_sshaccount ADD COLUMN protocol_type varchar(20) NOT NULL DEFAULT 'ssh'"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_add_access_token"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_columns_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="sshaccount",
                    name="auth_token",
                    field=models.UUIDField(null=True),
                ),
                migrations.AddField(
                    model_name="sshaccount",
                    name="protocol_type",
                    field=models.CharField(
                        choices=[("ssh", "SSH"), ("shadowlink", "ShadowLink")],
                        default="ssh",
                        max_length=20,
                    ),
                ),
            ],
        ),
    ]
