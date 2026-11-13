"""Synthetic operation prefill is repeatable, additive and customer-scoped."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from engagements.models import Contact
from engagements.services import capture_report
from testsupport.csrf_cases import workflow_fixture
from .models import InventoryItem
from .walkthrough import prefill_operations, EXAMPLES


class OperationPrefillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=workflow_fixture()

    def setUp(self):
        self.client.force_login(self.f.user)

    def test_adds_three_unknown_operations_with_owner_and_audit(self):
        added,kept=prefill_operations(self.f.customer,self.f.user,self.f.person)
        self.assertEqual(len(added),3)
        self.assertEqual(kept,[])
        for example in EXAMPLES:
            item=InventoryItem.objects.get(customer=self.f.customer,name=example['name'])
            self.assertEqual(item.owner,self.f.person)
            self.assertEqual(item.state,'unknown')
            self.assertEqual(item.criticality,'unknown')
            self.assertIsNone(item.impact)
            self.assertTrue(item.notes)
        self.assertEqual(self.f.customer.inventory_events.count(),3)

    def test_manual_and_archived_matches_are_not_overwritten(self):
        original=InventoryItem.objects.create(customer=self.f.customer,kind='operation',name='  BIWEEKLY   PAYROLL ',archived=True,notes='Keep my edited facts')
        added,kept=prefill_operations(self.f.customer,self.f.user)
        self.assertEqual(len(added),2)
        self.assertEqual(kept,['Biweekly payroll'])
        original.refresh_from_db()
        self.assertTrue(original.archived)
        self.assertEqual(original.notes,'Keep my edited facts')
        self.assertIsNone(original.owner)

    def test_repeat_after_renaming_preserves_records_and_captures(self):
        report=capture_report(engagement=self.f.engagement,user=self.f.user)
        snapshot=report.snapshot
        assessment_inventory=self.f.assessment.inventory_snapshot
        prefill_operations(self.f.customer,self.f.user)
        item=InventoryItem.objects.get(customer=self.f.customer,name='Biweekly payroll')
        item.name='Edited payroll operation'
        item.archived=True
        item.save()
        added,kept=prefill_operations(self.f.customer,self.f.user,self.f.person)
        self.assertEqual(added,[])
        self.assertEqual(len(kept),3)
        self.assertEqual(self.f.customer.inventory_events.count(),3)
        item.refresh_from_db()
        self.assertIsNone(item.owner)
        report.refresh_from_db()
        self.f.assessment.refresh_from_db()
        self.assertEqual(report.snapshot,snapshot)
        self.assertEqual(self.f.assessment.inventory_snapshot,assessment_inventory)

    def test_authentication_scope_synthetic_gate_and_read_only_get(self):
        url=reverse('inventory_walkthrough_operations',args=[self.f.customer.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        stranger=get_user_model().objects.create_superuser('prefill-outsider','outside@example.test','synthetic-only')
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(url,{}).status_code,404)
        with self.assertRaises(PermissionDenied):
            prefill_operations(self.f.customer,stranger)
        self.client.force_login(self.f.user)
        self.f.customer.synthetic=False
        self.f.customer.save()
        self.assertEqual(self.client.post(url,{}).status_code,404)
        with self.assertRaises(ValidationError):
            prefill_operations(self.f.customer,self.f.user)
        page=self.client.get(reverse('inventory_detail',args=[self.f.customer.pk])+'?kind=operation')
        self.assertNotContains(page,'Add remaining cafe operations')

    def test_forged_owner_fails_without_partial_records(self):
        foreign=Contact.objects.create(first_name='Foreign',last_name='Owner',email='foreign@example.test')
        before=self.f.customer.inventory_items.count()
        url=reverse('inventory_walkthrough_operations',args=[self.f.customer.pk])
        self.assertEqual(self.client.post(url,{'owner':foreign.pk}).status_code,400)
        self.assertEqual(self.f.customer.inventory_items.count(),before)
        with self.assertRaises(ValidationError):
            prefill_operations(self.f.customer,self.f.user,foreign)
        self.assertEqual(self.f.customer.inventory_items.count(),before)
