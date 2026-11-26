from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from .models import Baseline


class BaselineErrorResponseTests(TestCase):
    def test_invalid_and_rejected_mutations_preserve_baseline(self):
        user=get_user_model().objects.create_user('synthetic-errors',is_staff=True)
        self.client.force_login(user)
        base=Baseline.objects.create(version='synthetic-draft',coverage_gaps='Synthetic',snapshot={},created_by=user)
        cases=[('create_baseline',[],{'version':'new','coverage_gaps':'Synthetic'},'create_baseline'),
               ('approve_baseline',[base.pk],{'note':'Synthetic','confirmed':'on'},'approve_baseline'),
               ('revise_baseline',[base.pk],{'version':'replacement','coverage_gaps':'Synthetic','revision_note':'Synthetic'},'revise_draft')]
        for name,args,data,service in cases:
            self.assertEqual(self.client.post(reverse(name,args=args),{}).status_code,400)
            for error in ([ValidationError('Synthetic rejection'),IntegrityError()] if service!='approve_baseline' else [ValidationError('Synthetic rejection')]):
                with patch('library.views.services.'+service,side_effect=error):
                    self.assertEqual(self.client.post(reverse(name,args=args),data).status_code,400)
        base.refresh_from_db();self.assertIsNone(base.approved_at);self.assertIsNone(base.superseded_by_id)
