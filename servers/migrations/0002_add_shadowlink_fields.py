import django.core.validators
from django.db import migrations, models


def add_columns_if_missing(apps, schema_editor):
    """Idempotent column additions for partially-migrated databases."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'servers_server'"
        )
        existing = {row[0] for row in cursor.fetchall()}

    columns = {
        "protocol_type": "ALTER TABLE servers_server ADD COLUMN protocol_type varchar(20) NOT NULL DEFAULT 'ssh'",
        "shadowlink_api_key": "ALTER TABLE servers_server ADD COLUMN shadowlink_api_key varchar(128) NOT NULL DEFAULT ''",
        "shadowlink_bridge_port": "ALTER TABLE servers_server ADD COLUMN shadowlink_bridge_port integer NOT NULL DEFAULT 9090",
        "shadowlink_domain": "ALTER TABLE servers_server ADD COLUMN shadowlink_domain varchar(255) NOT NULL DEFAULT ''",
        "shadowlink_port": "ALTER TABLE servers_server ADD COLUMN shadowlink_port integer NOT NULL DEFAULT 8443",
        "shadowlink_ws_path": "ALTER TABLE servers_server ADD COLUMN shadowlink_ws_path varchar(100) NOT NULL DEFAULT '/ws'",
    }

    with connection.cursor() as cursor:
        for col_name, sql in columns.items():
            if col_name not in existing:
                cursor.execute(sql)


class Migration(migrations.Migration):

    dependencies = [
        ("servers", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_columns_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="server",
                    name="protocol_type",
                    field=models.CharField(
                        choices=[("ssh", "SSH"), ("shadowlink", "ShadowLink")],
                        default="ssh",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="server",
                    name="shadowlink_api_key",
                    field=models.CharField(
                        blank=True,
                        help_text="API key for authenticating with the ShadowLink bridge.",
                        max_length=128,
                    ),
                ),
                migrations.AddField(
                    model_name="server",
                    name="shadowlink_bridge_port",
                    field=models.PositiveIntegerField(
                        default=9090,
                        help_text="Port for the ShadowLink bridge API (localhost only).",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(65535),
                        ],
                    ),
                ),
                migrations.AddField(
                    model_name="server",
                    name="shadowlink_domain",
                    field=models.CharField(
                        blank=True,
                        help_text="Domain pointing to this server (for TLS SNI and CDN).",
                        max_length=255,
                    ),
                ),
                migrations.AddField(
                    model_name="server",
                    name="shadowlink_port",
                    field=models.PositiveIntegerField(
                        default=8443,
                        help_text="Port the ShadowLink Go server listens on.",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(65535),
                        ],
                    ),
                ),
                migrations.AddField(
                    model_name="server",
                    name="shadowlink_ws_path",
                    field=models.CharField(
                        default="/ws",
                        help_text="WebSocket path for ShadowLink connections.",
                        max_length=100,
                    ),
                ),
            ],
        ),
    ]
