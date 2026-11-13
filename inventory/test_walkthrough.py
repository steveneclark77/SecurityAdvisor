"""Complete synthetic inventory stays additive, repeatable and customer-scoped."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from engagements.models import Contact
from engagements.services import capture_report
from testsupport.csrf_cases import workflow_fixture
from .models import InventoryItem, InventoryConnection, InventoryFollowUp, InventoryEvent, ITEM_KINDS
from .walkthrough import prefill_inventory
from .walkthrough_data import ITEMS, FOLLOWUPS


class InventoryPrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=workflow_fixture()

    def setUp(self):
        self.client.force_login(self.f.user)

    def test_adds_all_types_relationships_questions_owner_and_audit(self):
        counts=prefill_inventory(self.f.customer,self.f.user,self.f.person)
        self.assertEqual(counts['items_added'],18)
        self.assertEqual(counts['connections_added'],15)
        self.assertEqual(counts['followups_added'],8)
        self.assertEqual({item['kind'] for item in ITEMS},set(dict(ITEM_KINDS)))
        for example in ITEMS:
            item=InventoryItem.objects.get(customer=self.f.customer,kind=example['kind'],name=example['name'])
            self.assertEqual(item.owner,self.f.person)
            self.assertEqual(item.state,'unknown')
            self.assertEqual(item.criticality,'unknown')
            self.assertIsNone(item.impact)
            self.assertTrue(item.notes)
        self.assertEqual(self.f.customer.inventory_events.count(),41)
        self.assertEqual(self.f.customer.inventory_followups.filter(owner=self.f.person,status='open').count(),8)
        for link in self.f.customer.inventory_connections.all():
            self.assertEqual(link.source.customer_id,self.f.customer.pk)
            self.assertEqual(link.target.customer_id,self.f.customer.pk)
            self.assertEqual(link.state,'unknown')

    def test_manual_and_archived_matches_are_not_overwritten(self):
        original=InventoryItem.objects.create(customer=self.f.customer,kind='operation',name='  BIWEEKLY   PAYROLL ',archived=True,notes='Keep my edited facts')
        counts=prefill_inventory(self.f.customer,self.f.user)
        self.assertEqual(counts['items_added'],17)
        self.assertEqual(counts['items_kept'],1)
        self.assertGreater(counts['skipped'],0)
        original.refresh_from_db()
        self.assertTrue(original.archived)
        self.assertEqual(original.notes,'Keep my edited facts')
        self.assertIsNone(original.owner)
        self.assertFalse(InventoryConnection.objects.filter(customer=self.f.customer,source=original).exists())

    def test_repeat_after_item_link_question_edits_preserves_captures(self):
        report=capture_report(engagement=self.f.engagement,user=self.f.user)
        snapshot=report.snapshot
        assessment_inventory=self.f.assessment.inventory_snapshot
        prefill_inventory(self.f.customer,self.f.user)
        item=InventoryItem.objects.get(customer=self.f.customer,name='Biweekly payroll')
        item.name='Edited payroll operation'
        item.archived=True
        item.save()
        link=InventoryConnection.objects.get(customer=self.f.customer,source__name='Orders and payments',target__name='Hosted point-of-sale application')
        link.details='Consultant changed this dependency'
        link.archived=True
        link.save()
        question=InventoryFollowUp.objects.get(customer=self.f.customer,question=FOLLOWUPS[0][2])
        question.question='Edited question'
        question.status='resolved'
        question.response='Confirmed synthetic facts'
        question.save()
        counts=prefill_inventory(self.f.customer,self.f.user,self.f.person)
        self.assertEqual([counts[key] for key in ['items_added','connections_added','followups_added']],[0,0,0])
        self.assertEqual(self.f.customer.inventory_events.count(),41)
        item.refresh_from_db()
        link.refresh_from_db()
        question.refresh_from_db()
        self.assertIsNone(item.owner)
        self.assertTrue(link.archived)
        self.assertEqual(link.details,'Consultant changed this dependency')
        self.assertEqual(question.status,'resolved')
        self.assertEqual(question.question,'Edited question')
        report.refresh_from_db()
        self.f.assessment.refresh_from_db()
        self.assertEqual(report.snapshot,snapshot)
        self.assertEqual(self.f.assessment.inventory_snapshot,assessment_inventory)

    def test_v1_renamed_operation_is_recognized(self):
        item=InventoryItem.objects.create(customer=self.f.customer,kind='operation',name='Previously renamed payroll',notes='Preserved v1 facts')
        InventoryEvent.objects.create(customer=self.f.customer,actor=self.f.user,description='Legacy synthetic operation',details={'after':{'id':item.pk},'walkthrough':{'key':'harbor-payroll','version':1}})
        counts=prefill_inventory(self.f.customer,self.f.user)
        self.assertEqual(counts['items_added'],17)
        self.assertFalse(InventoryItem.objects.filter(customer=self.f.customer,name='Biweekly payroll').exists())
        item.refresh_from_db()
        self.assertEqual(item.notes,'Preserved v1 facts')

    def test_kind_matching_and_ambiguous_endpoints(self):
        provider=InventoryItem.objects.create(customer=self.f.customer,kind='provider',name='Dropbox',notes='Do not repurpose this record')
        for name in ['Cafe network','Cafe business network']:
            InventoryItem.objects.create(customer=self.f.customer,kind='network',name=name)
        counts=prefill_inventory(self.f.customer,self.f.user)
        self.assertTrue(InventoryItem.objects.filter(customer=self.f.customer,kind='software',name='Dropbox').exists())
        self.assertGreater(counts['skipped'],0)
        self.assertFalse(InventoryConnection.objects.filter(customer=self.f.customer,target=provider).exists())
        self.assertFalse(InventoryConnection.objects.filter(customer=self.f.customer,source__name__in=['Cafe network','Cafe business network']).exists())
        provider.refresh_from_db()
        self.assertEqual(provider.notes,'Do not repurpose this record')

    def test_authentication_scope_synthetic_gate_and_read_only_get(self):
        url=reverse('inventory_walkthrough_prefill',args=[self.f.customer.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        stranger=get_user_model().objects.create_superuser('prefill-outsider','outside@example.test','synthetic-only')
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url,{}).status_code,404)
        with self.assertRaises(PermissionDenied):
            prefill_inventory(self.f.customer,stranger)
        self.client.force_login(self.f.user)
        self.f.customer.synthetic=False
        self.f.customer.save()
        self.assertEqual(self.client.post(url,{}).status_code,404)
        with self.assertRaises(ValidationError):
            prefill_inventory(self.f.customer,self.f.user)
        page=self.client.get(reverse('inventory_detail',args=[self.f.customer.pk]))
        self.assertNotContains(page,'Add missing cafe inventory')

    def test_forged_owner_fails_without_partial_records(self):
        foreign=Contact.objects.create(first_name='Foreign',last_name='Owner',email='foreign@example.test')
        before=self.f.customer.inventory_items.count()
        url=reverse('inventory_walkthrough_prefill',args=[self.f.customer.pk])
        self.assertEqual(self.client.post(url,{'owner':foreign.pk}).status_code,400)
        self.assertEqual(self.f.customer.inventory_items.count(),before)
        with self.assertRaises(ValidationError):
            prefill_inventory(self.f.customer,self.f.user,foreign)
        self.assertEqual(self.f.customer.inventory_items.count(),before)
