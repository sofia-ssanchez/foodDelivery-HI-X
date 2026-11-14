"""Run once for cron, or continuously in a dedicated worker."""
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from dispatch.tasks import check_stalled_orders


class Command(BaseCommand):
    help = "Expire unanswered offers and retry waiting orders."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=float, default=30)

    def handle(self, *args, **options):
        if options["interval"] <= 0:
            raise CommandError("--interval must be positive.")
        try:
            while True:
                close_old_connections()
                expired = check_stalled_orders()
                self.stdout.write(f"Expired {expired} offer(s).")
                if not options["loop"]:
                    return
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Stopped stalled-order worker.")
