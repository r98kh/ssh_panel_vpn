import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("servers", "0001_initial"),
    ]

    operations = [
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
    ]
