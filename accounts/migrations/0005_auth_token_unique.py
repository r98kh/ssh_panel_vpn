import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_populate_auth_tokens"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sshaccount",
            name="auth_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                help_text="Authentication token for ShadowLink protocol.",
                unique=True,
            ),
        ),
    ]
