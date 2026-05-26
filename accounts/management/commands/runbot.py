from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the Telegram bot for SSH VPN account sales."

    def handle(self, *args, **options):
        from bot.telegram_bot import run_bot
        run_bot()
