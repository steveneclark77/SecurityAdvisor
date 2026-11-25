from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from news.calibration import build_calibration


class Command(BaseCommand):
    help='Build an evaluated calibration version from human feedback. Never activates it or enables autonomy.'

    def add_arguments(self,parser):
        parser.add_argument('--name',required=True)
        parser.add_argument('--admin',required=True,help='Active app superuser username attributed to the build.')

    def handle(self,*args,**options):
        actor=get_user_model().objects.filter(username=options['admin'],is_active=True,is_superuser=True).first()
        if not actor:
            raise CommandError('Choose an active app admin.')
        try:
            version=build_calibration(options['name'],actor)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        eligible=sum(row['eligible'] for row in version.metrics['buckets'].values())
        self.stdout.write(f'Calibration {version.pk}: {eligible} eligible buckets. Activate explicitly in app admin; autonomy unchanged.')
