import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from library.models import Baseline
from news.ingestion import scan_source
from news.models import Source


class Command(BaseCommand):
    help = 'Collect RSS/Atom candidates after baseline approval. --loop repeats daily; no library/customer changes.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            if not Baseline.objects.filter(approved_at__isnull=False).exists():
                if not options['loop']:
                    raise CommandError('Approve a baseline before scanning news.')
                self.stdout.write('Waiting for an approved baseline; no feeds requested.')
            else:
                failures = 0
                for source_id in Source.objects.filter(enabled=True).values_list('pk', flat=True):
                    scan = scan_source(source_id)
                    failures += scan.status == 'failed'
                    self.stdout.write(f'Source {source_id}: {scan.status}, {scan.created_count} new candidates')
                if failures and not options['loop']:
                    raise CommandError(f'{failures} feed(s) failed; inspect News > Scans in admin.')
            if not options['loop']:
                return
            time.sleep(86400)
            # Recycle idle worker connections between cycles, never a caller
            # transaction when scan_news is invoked as a one-shot command.
            close_old_connections()
