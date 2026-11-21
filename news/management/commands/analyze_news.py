"""Explicit manual selection is independent of the automatic-analysis switch."""
import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from news.analysis import queue_articles, process_run, recover_expired, policy_key
from news.models import Article, AnalysisRun


class Command(BaseCommand):
    help = 'Queue/analyze public article revisions for review. Never automatically accepts proposals.'

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument('--article',type=int,nargs='+',help='One or more Article IDs, not Issue IDs.')
        selection.add_argument('--all-unanalyzed',action='store_true')
        selection.add_argument('--queued',action='store_true',help='Process already queued runs for the current policy.')
        parser.add_argument('--queue-only',action='store_true',help='Save jobs without calling the provider.')
        parser.add_argument('--retry-failed',action='store_true',help='Explicit retry, bounded by NEWS_ANALYSIS_MAX_ATTEMPTS per input/policy.')
        parser.add_argument('--max-records',type=int,default=50,help='Bounded batch size (1–500); repeat to drain all.')
        parser.add_argument('--drain',action='store_true',help='Process repeated bounded batches until selected work is exhausted or a limit/failure stops the command.')
        parser.add_argument('--loop',action='store_true',help='Automatic worker; stays idle unless NEWS_ANALYSIS_ENABLED=true.')

    def handle(self,*args,**options):
        if not 1<=options['max_records']<=500:
            raise CommandError('--max-records must be between 1 and 500.')
        if options['loop'] and (options['article'] or options['queued'] or options['all_unanalyzed'] or options['queue_only'] or options['retry_failed'] or options['drain']):
            raise CommandError('--loop cannot be combined with manual selection/retry options.')
        if not options['loop'] and not (options['article'] or options['all_unanalyzed'] or options['queued']):
            raise CommandError('Select --article ID [ID ...], --all-unanalyzed or --queued.')
        while True:
            if options['loop'] and not settings.NEWS_ANALYSIS_ENABLED:
                self.stdout.write('Automatic analysis is disabled; no database or provider requests.')
            else:
                created=[]
                run_ids=[]
                ids=options['article']
                if ids and Article.objects.filter(pk__in=ids).count()!=len(set(ids)):
                    raise CommandError('One or more Article IDs do not exist.')
                recover_expired()
                if not options['queued']:
                    created = queue_articles(ids,retry_failed=options['retry_failed'],limit=options['max_records'])
                    self.stdout.write(f'Queued {len(created)} article revision(s).')
                if not options['queue_only']:
                    queued = AnalysisRun.objects.filter(status='queued',policy_key=policy_key())
                    if not options['queued']:
                        current=Article.objects.all()
                        if ids:
                            current=current.filter(pk__in=ids)
                        queued=queued.filter(revision_id__in=current.values('current_revision_id'))
                    failed=0
                    run_ids=list(queued.order_by('pk').values_list('pk',flat=True)[:options['max_records']])
                    for run_id in run_ids:
                        try:
                            run=process_run(run_id)
                            if run:
                                failed+=run.status=='failed'
                                self.stdout.write(f'Analysis {run.pk}: {run.status}; proposals require review.')
                        except ValidationError as exc:
                            if not options['loop']:
                                raise CommandError('; '.join(exc.messages)) from exc
                            self.stderr.write('; '.join(exc.messages))
                            break
                    if failed and not options['loop']:
                        raise CommandError(f'{failed} analysis run(s) failed; inspect News > Analysis runs. Retry explicitly.')
            if not options['loop']:
                if options['drain'] and (created or run_ids):
                    continue
                return
            time.sleep(60)
            close_old_connections()
