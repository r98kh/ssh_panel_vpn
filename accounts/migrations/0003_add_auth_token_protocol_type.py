import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_add_access_token"),
    ]

    operations = [
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
    ]
