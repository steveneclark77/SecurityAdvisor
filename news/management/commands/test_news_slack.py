from django.core.management.base import BaseCommand,CommandError
from news.models import SlackTestRequest
from news.slack_tests import deliver_test


class Command(BaseCommand):
    help='Explicitly send one labeled Slack test message, even with no news items or daily digest disabled.'

    def handle(self,*args,**options):
        request=SlackTestRequest.objects.create(origin='cli')
        result=deliver_test(request.pk)
        text=f'Slack test {result.pk}: {result.message}'
        if result.status!='sent':
            raise CommandError(text)
        self.stdout.write(self.style.SUCCESS(text))
