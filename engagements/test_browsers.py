"""Read-only collection selection and customer/contact privacy regressions."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from testsupport.csrf_cases import workflow_fixture
from . import models as m


class RecordBrowserTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = workflow_fixture()
        cls.outsider = get_user_model().objects.create_superuser('unassigned-browser', 'outside@example.test', 'synthetic-only')
        cls.foreign_contact = m.Contact.objects.create(first_name='Private', last_name='Person', email='private@example.test')
        cls.foreign_contact.managers.add(cls.outsider)

    def setUp(self):
        self.client.force_login(self.f.user)

    def test_assessment_filters_selected_detail_and_frozen_guidance(self):
        url = reverse('assessment_detail', args=[self.f.assessment.pk])
        before = list(self.f.assessment.results.values_list('guidance', flat=True))
        response = self.client.get(url, {'selected': self.f.action.pk, 'q': 'PR-01', 'verification': 'not_tested'})
        self.assertEqual(response.context['selected'], self.f.action)
        self.assertContains(response, self.f.action.guidance['action']['instruction'])
        self.assertIn('verification=not_tested', response.context['records'][0]['url'])
        self.assertNotContains(self.client.get(url, {'q': 'no such action'}), 'Investigate and record result')
        self.assertEqual(before, list(self.f.assessment.results.values_list('guidance', flat=True)))

    def test_evidence_collections_filters_and_safe_invalid_selection(self):
        url = reverse('engagement_detail', args=[self.f.engagement.pk])
        for tab, record in [('requests', self.f.evidence_request), ('evidence', self.f.evidence), ('findings', self.f.finding)]:
            response = self.client.get(url, {'area': 'evidence', 'collection': tab, 'selected': record.pk})
            self.assertEqual(response.context['selected'], record)
            self.assertContains(response, record.title)
            self.assertContains(response, 'Record preview')
        response = self.client.get(url, {'area': 'evidence', 'collection': 'findings', 'priority': 'low'})
        self.assertEqual(response.context['page'].paginator.count, 0)
        response = self.client.get(url, {'area': 'evidence', 'collection': '../../other', 'selected': 'invalid', 'page': 'invalid'})
        self.assertEqual(response.context['collection'], 'requests')
        self.assertEqual(response.context['selected'], self.f.evidence_request)

    def test_superuser_requires_customer_assignment_for_every_browser(self):
        self.client.force_login(self.outsider)
        urls = [reverse('assessment_detail', args=[self.f.assessment.pk]),
                reverse('engagement_contacts', args=[self.f.engagement.pk]),
                reverse('engagement_detail', args=[self.f.engagement.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url, {'area': 'evidence', 'collection': 'findings', 'selected': self.f.finding.pk}).status_code, 404)

    def test_contact_selection_does_not_grant_management_or_reuse(self):
        directory = reverse('contact_index')
        response = self.client.get(directory, {'selected': self.foreign_contact.pk, 'q': 'Private'})
        self.assertIsNone(response.context['selected'])
        self.assertNotContains(response, self.foreign_contact.email)
        link = self.f.engagement.contact_links.first()
        person = link.contact
        person.managers.remove(self.f.user)
        response = self.client.get(directory, {'selected': person.pk})
        self.assertEqual(response.context['person'], person)
        self.assertNotContains(response, reverse('contact_edit', args=[person.pk]))
        url = reverse('engagement_contacts', args=[self.f.engagement.pk])
        response = self.client.get(url, {'collection': 'available', 'selected': person.pk})
        self.assertNotEqual(response.context['selected'], person)
        self.assertNotContains(response, reverse('contact_link', args=[self.f.engagement.pk, person.pk]))
        self.assertEqual(self.client.get(reverse('contact_edit', args=[person.pk])).status_code, 404)

    def test_contact_filters_retained_links_and_available_permission(self):
        url = reverse('engagement_contacts', args=[self.f.engagement.pk])
        person = m.Contact.objects.create(first_name='Reusable', last_name='Person', email='reuse@example.test')
        person.managers.add(self.f.user)
        response = self.client.get(url, {'collection': 'available', 'q': 'Reusable'})
        self.assertEqual(response.context['person'], person)
        self.assertContains(response, reverse('contact_link', args=[self.f.engagement.pk, person.pk]))
        link = self.f.engagement.contact_links.first()
        link.active = False
        link.primary = False
        link.save()
        response = self.client.get(url, {'visibility': 'inactive', 'selected': link.pk})
        self.assertEqual(response.context['selected'], link)
        self.assertContains(response, 'Unlinked/inactive')
        self.assertEqual(self.client.get(url, {'visibility': 'active'}).context['page'].paginator.count, 0)

    def test_pagination_preserves_collection_search_and_status(self):
        m.EvidenceRequest.objects.bulk_create([m.EvidenceRequest(engagement=self.f.engagement, title=f'Browser request {i}', instructions='Synthetic', owner=None) for i in range(55)])
        response = self.client.get(reverse('engagement_detail', args=[self.f.engagement.pk]), {'area': 'evidence', 'collection': 'requests', 'q': 'Browser request', 'status': 'requested', 'page': '2'})
        self.assertEqual(len(response.context['records']), 5)
        self.assertIn('collection=requests', response.context['previous_url'])
        self.assertIn('status=requested', response.context['previous_url'])
        self.assertIn('q=Browser+request', response.context['previous_url'])
        self.assertEqual(response.context['selected'], response.context['records'][0]['item'])

    def test_guessed_ids_and_queries_cannot_cross_engagements(self):
        customer = m.Customer.objects.create(name='Private browser customer')
        customer.assigned_users.add(self.outsider)
        engagement = m.Engagement.objects.create(customer=customer, **self.f.engagement_data)
        assessment = m.Assessment.objects.create(engagement=engagement, baseline=self.f.baseline, profile='Synthetic', created_by=self.outsider, applicability_rationale='Private')
        action = m.ActionResult.objects.create(assessment=assessment, control_code='PRIVATE', control_title='Private action', guidance={'action': {'instruction': 'Private guidance'}}, applicability_reason='Private')
        request = m.EvidenceRequest.objects.create(engagement=engagement, title='Private request', instructions='Private evidence', owner=None)
        evidence = m.Evidence.objects.create(engagement=engagement, title='Private evidence', notes='Private notes', provenance='Private source', collected_on=self.f.evidence.collected_on)
        finding = m.Finding.objects.create(engagement=engagement, assessment=assessment, **{**self.f.finding_data, 'title':'Private finding'})
        url = reverse('engagement_detail', args=[self.f.engagement.pk])
        for tab, obj in [('requests', request), ('evidence', evidence), ('findings', finding)]:
            response = self.client.get(url, {'area': 'evidence', 'collection': tab, 'selected': obj.pk, 'q': 'Private'})
            self.assertIsNone(response.context['selected'])
            self.assertNotContains(response, obj.title)
        response = self.client.get(reverse('assessment_detail', args=[self.f.assessment.pk]), {'selected': action.pk, 'q': 'PRIVATE'})
        self.assertIsNone(response.context['selected'])
        self.assertNotContains(response, 'Private guidance')

    def test_contact_full_name_search_and_read_only_gets(self):
        counts = (m.AuditEvent.objects.count(), m.Invite.objects.count(), m.ActionResult.objects.count())
        response = self.client.get(reverse('contact_index'), {'q': 'Alex Morgan'})
        self.assertEqual(response.context['person'], self.f.person)
        self.client.get(reverse('engagement_contacts', args=[self.f.engagement.pk]), {'visibility': 'invalid', 'page': 'invalid', 'selected': 'invalid'})
        self.client.get(reverse('assessment_detail', args=[self.f.assessment.pk]), {'applicability': 'invalid', 'verification': 'invalid'})
        self.client.get(reverse('engagement_detail', args=[self.f.engagement.pk]), {'area': 'evidence', 'collection': 'requests'})
        self.assertEqual(counts, (m.AuditEvent.objects.count(), m.Invite.objects.count(), m.ActionResult.objects.count()))
