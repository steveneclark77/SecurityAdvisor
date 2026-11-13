"""Single contact ownership, assignment boundaries, and preserved captures."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from testsupport.csrf_cases import workflow_fixture
from inventory.models import InventoryItem, InventoryFollowUp
from inventory.forms import ItemForm, FollowUpForm
from inventory.services import capture_inventory
from .models import Contact, Customer, Engagement, EngagementContact, EvidenceRequest
from .forms import ActionResultForm, EvidenceRequestForm, RemediationForm
from .ownership import owner_contacts
from .services import capture_report


class ContactOwnershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = workflow_fixture()
        cls.other_user = get_user_model().objects.create_superuser('owner-outsider', 'owner@example.test', 'synthetic-only')
        cls.customer = Customer.objects.create(name='Private synthetic customer')
        cls.customer.assigned_users.add(cls.other_user)
        cls.foreign_engagement = Engagement.objects.create(customer=cls.customer, **cls.f.engagement_data)
        cls.foreign = Contact.objects.create(first_name='Private', last_name='Owner', email='private@example.test')
        EngagementContact.objects.create(engagement=cls.foreign_engagement, contact=cls.foreign, roles=['technical'])
        cls.second = Engagement.objects.create(customer=cls.f.customer, **{**cls.f.engagement_data, 'title':'Second engagement'})
        cls.second_person = Contact.objects.create(first_name='Second', last_name='Owner', email='second@example.test')
        EngagementContact.objects.create(engagement=cls.second, contact=cls.second_person, roles=['technical'])

    def setUp(self):
        self.client.force_login(self.f.user)

    def test_all_five_forms_scope_owner_and_provide_notes(self):
        cases = [(ItemForm(instance=self.f.operation), 'owner', True),
                 (FollowUpForm(instance=self.f.followup, customer=self.f.customer), 'owner', True),
                 (ActionResultForm(instance=self.f.action, engagement=self.f.engagement), 'investigation_owner', False),
                 (EvidenceRequestForm(instance=self.f.evidence_request), 'owner', False),
                 (RemediationForm(instance=self.f.task, engagement=self.f.engagement), 'owner', False)]
        for form, name, inventory in cases:
            field = form.fields[name]
            self.assertFalse(field.required)
            self.assertIn('notes', form.fields)
            self.assertTrue(field.queryset.filter(pk=self.f.person.pk).exists())
            self.assertFalse(field.queryset.filter(pk=self.foreign.pk).exists())
            self.assertEqual(field.queryset.filter(pk=self.second_person.pk).exists(), inventory)
            with self.assertRaises(ValidationError):
                field.clean(str(self.foreign.pk))
            self.assertIn('data-owner-create', field.widget.attrs)

    def test_model_validation_and_post_reject_foreign_or_unlinked_owner(self):
        for obj, name in [(self.f.operation,'owner'), (self.f.followup,'owner'), (self.f.action,'investigation_owner'), (self.f.evidence_request,'owner'), (self.f.task,'owner')]:
            setattr(obj, name, self.foreign)
            with self.assertRaises(ValidationError):
                obj.full_clean()
        response = self.client.post(reverse('request_new', args=[self.f.engagement.pk]), {'title':'Invalid owner request','instructions':'Synthetic','owner':self.foreign.pk,'status':'requested'})
        self.assertEqual(response.status_code,400)
        self.assertFalse(EvidenceRequest.objects.filter(title='Invalid owner request').exists())

    def test_active_scope_must_match_the_same_link(self):
        self.f.link.active = False
        self.f.link.primary = False
        self.f.link.save()
        EngagementContact.objects.create(engagement=self.foreign_engagement, contact=self.f.person, active=True, roles=['technical'])
        self.assertFalse(owner_contacts(engagement_id=self.f.engagement.pk).filter(pk=self.f.person.pk).exists())
        self.assertTrue(owner_contacts(engagement_id=self.f.engagement.pk, retained_id=self.f.person.pk).filter(pk=self.f.person.pk).exists())

    def test_archived_owner_retained_but_not_newly_assigned_and_protected(self):
        self.f.person.archived = True
        self.f.person.save()
        current = EvidenceRequestForm(instance=self.f.evidence_request)
        self.assertTrue(current.fields['owner'].queryset.filter(pk=self.f.person.pk).exists())
        new = EvidenceRequestForm(instance=EvidenceRequest(engagement=self.f.engagement))
        self.assertFalse(new.fields['owner'].queryset.filter(pk=self.f.person.pk).exists())
        with self.assertRaises(ProtectedError):
            self.f.person.delete()

    def test_refresh_endpoint_requires_assignment_even_for_superusers(self):
        url = reverse('owner_choices')
        response = self.client.get(url, {'customer_id':self.f.customer.pk})
        ids = [row['id'] for row in response.json()['contacts']]
        self.assertIn(self.second_person.pk, ids)
        self.assertNotIn(self.foreign.pk, ids)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url, {'customer_id':self.f.customer.pk}).status_code,404)
        self.assertEqual(self.client.get(url, {'engagement_id':self.f.engagement.pk}).status_code,404)
        self.assertEqual(self.client.post(url, {}).status_code,405)

    def test_owner_and_notes_persist_and_captures_keep_names_after_contact_edit(self):
        response = self.client.post(reverse('inventory_item_edit', args=[self.f.operation.pk]), {'name':self.f.operation.name,'state':'unknown','criticality':'unknown','owner':self.f.person.pk,'notes':'Jordan assists; Alex is accountable.'})
        self.assertEqual(response.status_code,302)
        self.f.operation.refresh_from_db()
        self.assertEqual(self.f.operation.owner,self.f.person)
        captured = capture_inventory(self.f.customer)
        report = capture_report(engagement=self.f.engagement,user=self.f.user)
        self.f.person.first_name = 'Renamed'
        self.f.person.save()
        record = next(item for item in captured['items'] if item['id']==self.f.operation.pk)
        self.assertEqual(record['owner'], 'Alex Morgan')
        self.assertEqual(record['owner_contact']['id'], self.f.person.pk)
        self.assertEqual(record['notes'],'Jordan assists; Alex is accountable.')
        report.refresh_from_db()
        self.assertEqual(report.snapshot['findings'][0]['tasks'][0]['owner'], 'Alex Morgan')
        self.assertIsNone(self.f.action.investigation_owner)

    def test_create_contact_customer_context_checks_target_engagement(self):
        url = reverse('contact_new') + f'?customer={self.f.customer.pk}'
        data = {'first_name':'New','last_name':'Owner','email':'new@example.test','link_engagement':self.foreign_engagement.pk}
        response = self.client.post(url,data)
        self.assertFalse(Contact.objects.filter(email='new@example.test').exists())
        response = self.client.post(url,{**data,'link_engagement':self.second.pk})
        person = Contact.objects.get(email='new@example.test')
        self.assertEqual(response.url,reverse('contact_link',args=[self.second.pk,person.pk]))
