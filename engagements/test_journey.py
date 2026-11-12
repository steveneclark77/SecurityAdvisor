from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from . import models as m
from .journey import engagement_journey
from testsupport.csrf_cases import workflow_fixture


class JourneyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = workflow_fixture()

    def fresh_engagement(self, *, intake=True, contact=True):
        f = self.fixture
        customer = m.Customer.objects.create(name='Synthetic Journey Cafe')
        customer.assigned_users.add(f.user)
        engagement = m.Engagement.objects.create(customer=customer, **f.engagement_data)
        if contact:
            m.EngagementContact.objects.create(engagement=engagement, contact=f.person, roles=['business_owner'], active=True)
        response = m.Intake.objects.create(engagement=engagement, answers={'activities': 'Synthetic cafe'}, recommendation={}) if intake else None
        return engagement, response

    def test_initial_inventory_recommendation_and_factual_statuses(self):
        engagement, intake = self.fresh_engagement()
        journey = engagement_journey(engagement, intake)
        steps = {step['key']: step for phase in journey['phases'] for step in phase['steps']}
        self.assertEqual(len(steps), 7)
        self.assertEqual(journey['next']['key'], 'inventory')
        self.assertEqual(steps['scope']['action'], 'Edit')
        self.assertEqual(steps['intake']['action'], 'Review')
        self.assertEqual(steps['inventory']['action'], 'Start')
        self.assertEqual(steps['intake']['detail'], 'Customer response received')
        self.assertEqual(sum(step['recommended'] for step in steps.values()), 1)

    def test_contacts_and_optional_intake_guidance(self):
        engagement, _ = self.fresh_engagement(intake=False, contact=False)
        self.assertEqual(engagement_journey(engagement, None)['next']['key'], 'scope')
        m.EngagementContact.objects.create(engagement=engagement, contact=self.fixture.person, roles=['business_owner'], active=True)
        self.assertEqual(engagement_journey(engagement, None)['next']['key'], 'intake')
        from .services import issue_invite
        issue_invite(engagement=engagement, user=self.fixture.user, purpose='intake')
        self.assertEqual(engagement_journey(engagement, None)['next']['key'], 'inventory')
        from django.utils import timezone
        engagement.invite_set.update(expires_at=timezone.now())
        expired = engagement_journey(engagement, None)
        self.assertEqual(expired['next']['key'], 'intake')
        self.assertEqual(expired['phases'][0]['steps'][1]['state'], 'progress')

    def test_existing_work_counts_and_no_mutations_on_get(self):
        f = self.fixture
        self.client.force_login(f.user)
        before = (m.AuditEvent.objects.count(), m.Intake.objects.count(), m.Assessment.objects.count())
        response = self.client.get(reverse('engagement_detail', args=[f.engagement.pk]))
        self.assertEqual(response.status_code, 200)
        journey = response.context['journey']
        self.assertEqual(journey['next']['key'], 'remediation')
        self.assertEqual(journey['assessment_count'], 1)
        self.assertEqual(journey['open_information'], 1)
        self.assertEqual(before, (m.AuditEvent.objects.count(), m.Intake.objects.count(), m.Assessment.objects.count()))
        self.assertContains(response, 'Work status only')
        self.assertNotContains(response, 'Review pending')

    def test_customer_inventory_is_shared_but_unrelated_customer_work_is_excluded(self):
        engagement, intake = self.fresh_engagement()
        original = engagement_journey(engagement, intake)
        self.assertEqual(original['open_information'], 0)
        self.assertEqual(original['assessment_count'], 0)
        other = self.fixture.engagement
        self.assertEqual(engagement_journey(other, None)['open_information'], 1)

    def test_unassigned_superuser_cannot_view_any_work_area(self):
        user = get_user_model().objects.create_superuser('journey-outsider', password='synthetic-password')
        self.client.force_login(user)
        for area in ['scope', 'intake', 'assessments', 'evidence', 'remediation', 'reports', 'history', 'links']:
            self.assertEqual(self.client.get(reverse('engagement_detail', args=[self.fixture.engagement.pk]), {'area': area}).status_code, 404)

    def test_work_areas_are_whitelisted_and_mutations_keep_post_forms(self):
        self.client.force_login(self.fixture.user)
        url = reverse('engagement_detail', args=[self.fixture.engagement.pk])
        response = self.client.get(url, {'area': 'reports'})
        self.assertContains(response, 'id="work-reports"')
        self.assertContains(response, 'method="post"')
        self.assertEqual(self.client.get(url, {'area': '../../secrets'}).context['selected_area'], '')


    def test_unknown_inventory_does_not_gate_assessment_guidance(self):
        from inventory.models import InventoryItem
        engagement, intake = self.fresh_engagement()
        InventoryItem.objects.create(customer=engagement.customer, kind='operation', name='Synthetic payroll', state='unknown')
        journey = engagement_journey(engagement, intake)
        self.assertEqual(journey['next']['key'], 'assessments')
        inventory = next(step for phase in journey['phases'] for step in phase['steps'] if step['key'] == 'inventory')
        self.assertEqual(inventory['state'], 'progress')
        self.assertEqual(inventory['action'], 'Edit')

    def test_archived_inventory_does_not_imply_working_scope(self):
        from inventory.models import InventoryItem
        engagement, intake = self.fresh_engagement()
        InventoryItem.objects.create(customer=engagement.customer, kind='device', name='Archived synthetic laptop', archived=True)
        self.assertEqual(engagement_journey(engagement, intake)['next']['key'], 'inventory')


    def test_unplanned_findings_are_recommended_even_with_other_verified_tasks(self):
        f = self.fixture
        m.Remediation.objects.filter(finding__engagement=f.engagement).update(status='verified')
        finding = m.Finding.objects.create(engagement=f.engagement, assessment=f.assessment, **{**f.finding_data, 'title': 'Synthetic finding without a plan'})
        self.assertEqual(engagement_journey(f.engagement, None)['next']['key'], 'remediation')
        finding.risk_acceptance = 'Synthetic owner accepted this risk pending review'
        finding.save()
        self.assertEqual(engagement_journey(f.engagement, None)['next']['key'], 'evidence')


    def test_provider_only_inventory_still_recommends_recording_business_operations(self):
        from inventory.models import InventoryItem
        engagement, intake = self.fresh_engagement()
        InventoryItem.objects.create(customer=engagement.customer, kind='provider', name='Synthetic provider', state='reported', provenance='Synthetic customer interview')
        journey = engagement_journey(engagement, intake)
        self.assertEqual(journey['next']['key'], 'inventory')
        self.assertEqual(journey['next']['state'], 'progress')
        self.assertEqual(journey['next']['action'], 'Edit')
