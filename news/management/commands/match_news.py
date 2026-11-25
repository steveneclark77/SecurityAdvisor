import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from news.matching import process_pending


class Command(BaseCommand):
    help='Match cached article extractions in learning mode unless an app admin explicitly enabled calibrated autonomy.'

    def add_arguments(self,parser):
        parser.add_argument('--loop',action='store_true')
        parser.add_argument('--prepare-cache',action='store_true',help='Explicitly allow bounded embedding API calls, shared daily budget.')
        parser.add_argument('--max-records',type=int,default=50)

    def handle(self,*args,**options):
        if not 1<=options['max_records']<=200:
            raise CommandError('--max-records must be between 1 and 200.')
        while True:
            if not options['loop'] or settings.NEWS_ANALYSIS_ENABLED:
                try:
                    rows=process_pending(limit=options['max_records'],prepare=options['prepare_cache'] or options['loop'])
                    self.stdout.write(f'Assessed {len(rows)} proposal(s); learning mode remains human-reviewed.')
                except ValidationError as exc:
                    if not options['loop']:
                        raise CommandError('; '.join(exc.messages)) from exc
                    self.stderr.write('; '.join(exc.messages))
            if not options['loop']:
                return
            time.sleep(60)
            close_old_connections()
