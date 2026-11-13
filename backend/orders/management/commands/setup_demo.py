import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from orders.demo import reset_demo


class Command(BaseCommand):
    help = 'Back up the local SQLite database and replace its data with the demo baseline.'

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if not settings.DEBUG or db['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Demo setup requires DEBUG and a local SQLite database.')
        backup = Path('/tmp') / f'foodDelivery-before-demo-{datetime.now():%Y%m%d-%H%M%S}.sqlite3'
        with sqlite3.connect(db['NAME']) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        marker = settings.BASE_DIR / '.demo-enabled'
        was_enabled = marker.exists()
        marker.touch()
        try:
            result = reset_demo()
        except Exception:
            if not was_enabled:
                marker.unlink()
            raise
        self.stdout.write(f'Backup: {backup}')
        self.stdout.write(self.style.SUCCESS(str(result)))
