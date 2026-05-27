import uuid
from django.db import migrations


def populate_unique_auth_tokens(apps, schema_editor):
    SSHAccount = apps.get_model("accounts", "SSHAccount")
    for account in SSHAccount.objects.all():
        account.auth_token = uuid.uuid4()
        account.save(update_fields=["auth_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_add_auth_token_protocol_type"),
    ]

    operations = [
        migrations.RunPython(populate_unique_auth_tokens, migrations.RunPython.noop),
    ]
