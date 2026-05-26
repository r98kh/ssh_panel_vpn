"""
Telegram Bot Integration
=========================
Provides a Telegram bot for:
  - Purchasing SSH accounts (/buy)
  - Checking account status (/status)
  - Admin notifications on key events

Run standalone:  python manage.py runbot
"""
import logging
import os
import sys

import django

logger = logging.getLogger(__name__)


def _bootstrap_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sshvpn.settings")
    django.setup()


async def start(update, context):
    await update.message.reply_text(
        "Welcome to SSH VPN Bot!\n\n"
        "Commands:\n"
        "/plans - View available plans\n"
        "/buy <plan_id> <username> - Purchase an account\n"
        "/status <username> - Check account status\n"
        "/help - Show this message"
    )


async def help_cmd(update, context):
    await start(update, context)


async def plans_cmd(update, context):
    from plans.models import Plan

    active_plans = Plan.objects.filter(is_active=True)
    if not active_plans.exists():
        await update.message.reply_text("No plans available at the moment.")
        return

    lines = ["Available Plans:\n"]
    for p in active_plans:
        bw = f"{p.bandwidth_limit_gb} GB" if p.bandwidth_limit_gb else "Unlimited"
        lines.append(
            f"ID {p.id}: {p.name}\n"
            f"  Duration: {p.duration_days} days\n"
            f"  Price: {p.price} {p.currency}\n"
            f"  Max connections: {p.max_connections}\n"
            f"  Bandwidth: {bw}\n"
        )
    await update.message.reply_text("\n".join(lines))


async def buy_cmd(update, context):
    from accounts.services import create_account, AccountError
    from plans.models import Plan

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /buy <plan_id> <username>")
        return

    try:
        plan_id = int(args[0])
        username = args[1].lower().strip()
    except (ValueError, IndexError):
        await update.message.reply_text("Invalid arguments. Usage: /buy <plan_id> <username>")
        return

    try:
        plan = Plan.objects.get(pk=plan_id, is_active=True)
    except Plan.DoesNotExist:
        await update.message.reply_text(f"Plan {plan_id} not found.")
        return

    try:
        account = create_account(username=username, plan=plan)
    except AccountError as e:
        await update.message.reply_text(f"Error: {e}")
        return

    await update.message.reply_text(
        f"Account created!\n\n"
        f"Host: {account.server.ip_address}\n"
        f"Port: {account.server.ssh_port}\n"
        f"Username: {account.username}\n"
        f"Password: {account.password_display}\n"
        f"Expires: {account.expire_date:%Y-%m-%d %H:%M UTC}\n\n"
        f"Save this information — password won't be shown again."
    )


async def status_cmd(update, context):
    from accounts.models import SSHAccount

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /status <username>")
        return

    username = args[0].lower().strip()
    accounts = SSHAccount.objects.filter(username=username).exclude(
        status=SSHAccount.Status.DELETED
    ).select_related("server")

    if not accounts.exists():
        await update.message.reply_text(f"No account found for '{username}'.")
        return

    for acc in accounts:
        await update.message.reply_text(
            f"Account: {acc.username}\n"
            f"Server: {acc.server.ip_address}:{acc.server.ssh_port}\n"
            f"Status: {acc.get_status_display()}\n"
            f"Expires: {acc.expire_date:%Y-%m-%d %H:%M UTC}\n"
            f"Days remaining: {acc.days_remaining}\n"
        )


def send_admin_notification(message: str):
    """Fire-and-forget notification to admin chat (sync helper)."""
    import asyncio
    from telegram import Bot
    from django.conf import settings

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
    if not token or not chat_id:
        return

    async def _send():
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send())
        else:
            loop.run_until_complete(_send())
    except Exception:
        logger.exception("Failed to send Telegram notification")


def run_bot():
    _bootstrap_django()
    from django.conf import settings
    from telegram.ext import ApplicationBuilder, CommandHandler

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        print("TELEGRAM_BOT_TOKEN not set. Exiting.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("plans", plans_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    print("Telegram bot started. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
