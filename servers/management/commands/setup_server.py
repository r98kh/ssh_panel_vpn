"""
Management command: setup_server
=================================
Creates a new SSH server record and provisions a default test user on it.

Usage:
    python manage.py setup_server \
        --name "Germany-1" \
        --ip 1.2.3.4 \
        --ssh-port 22 \
        --ssh-user root \
        --ssh-key /root/.ssh/id_rsa \
        --location "Frankfurt, DE" \
        --max-users 100 \
        --default-username test_user \
        --default-password MyP@ss123 \
        --default-days 30 \
        --default-max-conns 2
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta

from servers.models import Server
from servers.ssh import SSHManager
from accounts.models import SSHAccount, generate_password
from plans.models import Plan


class Command(BaseCommand):
    help = "Create an SSH server and provision a default user on it."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Server display name.")
        parser.add_argument("--ip", required=True, help="Server IP address.")
        parser.add_argument("--ssh-port", type=int, default=22)
        parser.add_argument("--ssh-user", default="root")
        parser.add_argument("--ssh-key", default="", help="Path to SSH private key on panel host.")
        parser.add_argument("--location", default="", help="e.g. Frankfurt, DE")
        parser.add_argument("--max-users", type=int, default=100)

        parser.add_argument("--default-username", default="default_user", help="Username for the default account.")
        parser.add_argument("--default-password", default="", help="Password (auto-generated if omitted).")
        parser.add_argument("--default-days", type=int, default=30, help="Account validity in days.")
        parser.add_argument("--default-max-conns", type=int, default=1, help="Max concurrent connections.")
        parser.add_argument("--default-bandwidth-gb", type=int, default=0, help="Bandwidth limit (0=unlimited).")

        parser.add_argument("--skip-ssh-test", action="store_true", help="Skip SSH connectivity test.")
        parser.add_argument("--skip-user", action="store_true", help="Only create server, skip default user.")

    def handle(self, *args, **options):
        name = options["name"]
        ip = options["ip"]
        ssh_port = options["ssh_port"]
        ssh_user = options["ssh_user"]
        ssh_key = options["ssh_key"]
        location = options["location"]
        max_users = options["max_users"]

        # --- Step 1: Create or get server ---
        server, created = Server.objects.get_or_create(
            ip_address=ip,
            defaults={
                "name": name,
                "ssh_port": ssh_port,
                "ssh_user": ssh_user,
                "ssh_key_path": ssh_key,
                "protocol_type": "ssh",
                "location": location,
                "max_users": max_users,
                "status": Server.Status.ACTIVE,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Server created: {server}"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠ Server already exists: {server}"))
            server.name = name
            server.ssh_port = ssh_port
            server.ssh_user = ssh_user
            server.ssh_key_path = ssh_key
            server.location = location
            server.max_users = max_users
            server.save()
            self.stdout.write("  Updated server fields.")

        # --- Step 2: Test SSH connectivity ---
        if not options["skip_ssh_test"]:
            self.stdout.write("  Testing SSH connection...")
            ssh = SSHManager(
                host=server.ip_address,
                port=server.ssh_port,
                username=server.ssh_user,
                key_path=server.ssh_key_path,
            )
            try:
                ssh.connect()
                result = ssh.run("echo ok")
                if not result.ok:
                    raise CommandError(f"SSH connected but test command failed: {result.stderr}")
                self.stdout.write(self.style.SUCCESS("  ✓ SSH connection successful."))
                ssh.disconnect()
            except Exception as e:
                raise CommandError(f"SSH connection failed: {e}")

        if options["skip_user"]:
            self.stdout.write(self.style.SUCCESS("Done (skipped user creation)."))
            return

        # --- Step 3: Create default user ---
        username = options["default_username"]
        password = options["default_password"] or generate_password()
        days = options["default_days"]
        max_conns = options["default_max_conns"]
        bw_limit = options["default_bandwidth_gb"]
        expire_date = timezone.now() + timedelta(days=days)

        if SSHAccount.objects.filter(username=username, server=server).exclude(status=SSHAccount.Status.DELETED).exists():
            self.stdout.write(self.style.WARNING(f"⚠ User '{username}' already exists on {server.name}. Skipping."))
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        plan = Plan.objects.filter(is_active=True).order_by("duration_days").first()
        if not plan:
            plan = Plan.objects.create(
                name="Default",
                duration_days=days,
                price=0,
                max_connections=max_conns,
                bandwidth_limit_gb=bw_limit,
            )
            self.stdout.write(f"  Created default plan: {plan}")

        # Provision on remote server via SSH
        self.stdout.write(f"  Creating user '{username}' on {server.ip_address}...")
        ssh = SSHManager(
            host=server.ip_address,
            port=server.ssh_port,
            username=server.ssh_user,
            key_path=server.ssh_key_path,
        )
        try:
            ssh.connect()
            if ssh.user_exists(username):
                self.stdout.write(f"  OS user '{username}' already exists on server, skipping useradd.")
            else:
                result = ssh.create_user(username, password)
                if not result.ok:
                    raise CommandError(f"Failed to create OS user: {result.stderr}")

            ssh.set_expiry(username, expire_date.strftime("%Y-%m-%d"))
            ssh.set_max_logins(username, max_conns)
            if bw_limit > 0:
                ssh.setup_traffic_accounting(username)
            ssh.disconnect()
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f"Remote provisioning failed: {e}")

        # Save to database
        account = SSHAccount.objects.create(
            username=username,
            password_display=password,
            server=server,
            plan=plan,
            protocol_type="ssh",
            status=SSHAccount.Status.ACTIVE,
            expire_date=expire_date,
            max_connections=max_conns,
            bandwidth_limit_gb=bw_limit,
            note="Default account created by setup_server command.",
        )

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 50))
        self.stdout.write(self.style.SUCCESS("  SERVER + DEFAULT USER CREATED SUCCESSFULLY"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"  Server:   {server.name} ({server.ip_address})")
        self.stdout.write(f"  Username: {account.username}")
        self.stdout.write(f"  Password: {password}")
        self.stdout.write(f"  Port:     {server.ssh_port}")
        self.stdout.write(f"  Expires:  {expire_date.strftime('%Y-%m-%d')}")
        self.stdout.write(f"  Max Conn: {max_conns}")
        self.stdout.write(self.style.SUCCESS("=" * 50))
