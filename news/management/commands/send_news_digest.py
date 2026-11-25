import time
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from news.digest import send_digest
from news.models import DigestDelivery
from news.slack_tests import configuration_status,process_test_requests


class Command(BaseCommand):
    help='Daily 09:00 America/Los_Angeles Slack digest, including weekends. No message when no new events.'

    def add_arguments(self,parser):
        parser.add_argument('--loop',action='store_true')
        parser.add_argument('--now',action='store_true',help='Explicit manual send, ignoring default-off/schedule.')
        parser.add_argument('--retry',action='store_true',help='Retry a known failed preflight; never an uncertain POST.')
        parser.add_argument('--resolve-sent',type=int,help='Operator confirms a delivery ID was already posted; no message sent.')
        parser.add_argument('--confirm-not-sent',type=int,help='Operator confirmed no message in Slack; make an uncertain delivery retryable.')

    def handle(self,*args,**options):
        if options['resolve_sent'] or options['confirm_not_sent']:
            if options['loop'] or options['now'] or options['retry'] or (options['resolve_sent'] and options['confirm_not_sent']):
                raise CommandError('Use one reconciliation flag alone, after checking Slack.')
            pk=options['resolve_sent'] or options['confirm_not_sent']
            updated=DigestDelivery.objects.filter(pk=pk,status__in=['unknown','sending']).update(
                status='sent' if options['resolve_sent'] else 'failed',error='Operator reconciled Slack delivery from CLI.')
            self.stdout.write(f'Reconciled {updated} delivery record(s); no message sent.')
            return
        self.stdout.write(configuration_status())
        while True:
            if options['loop']:
                for result in process_test_requests():
                    self.stdout.write(f'Slack test {result.pk}: {result.message}')
            try:
                if options['now'] or settings.NEWS_SLACK_DIGEST_ENABLED:
                    delivery=send_digest(force=options['now'],retry=options['retry'])
                    self.stdout.write(f'Digest: {delivery.status if delivery else "nothing due"}')
            except ValidationError as exc:
                if not options['loop']:
                    raise CommandError('; '.join(exc.messages)) from exc
                self.stderr.write('; '.join(exc.messages))
            if not options['loop']:
                return
            time.sleep(60)
            close_old_connections()
