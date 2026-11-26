from django.core.management.base import BaseCommand
from news.openai_tests import configuration_status,test_connection


class Command(BaseCommand):
    help='Explicitly test analysis and embedding model access with two small synthetic requests (API charges may apply).'

    def handle(self,*args,**options):
        self.stdout.write(configuration_status())
        self.stdout.write(self.style.SUCCESS(test_connection()))
