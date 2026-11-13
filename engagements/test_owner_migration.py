"""Owner conversion preserves records and refuses unexpected text rather than guessing."""
import os
import subprocess
import sys
from django.test import SimpleTestCase
from testsupport.migration_database import ISOLATED_DATABASE


class OwnerMigrationTests(SimpleTestCase):
    def test_conversion_preserves_history_and_refuses_unexpected_text(self):
        script = ISOLATED_DATABASE + r'''
with temporary_database():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    before = [('engagements', '0008_finding_inventory_items'), ('inventory', '0001_initial')]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    apps = executor.loader.project_state(before).apps
    user = apps.get_model('auth', 'User').objects.create(username='synthetic-owner-migration')
    customer = apps.get_model('engagements', 'Customer').objects.create(name='Synthetic migration cafe')
    engagement = apps.get_model('engagements', 'Engagement').objects.create(customer=customer, title='Synthetic migration engagement')
    baseline = apps.get_model('library', 'Baseline').objects.create(version='owner-test', created_by=user, snapshot={})
    frozen = {'items': [{'id': 1, 'owner': 'Historical name'}]}
    assessment = apps.get_model('engagements', 'Assessment').objects.create(engagement=engagement, baseline=baseline, created_by=user, inventory_snapshot=frozen)
    request = apps.get_model('engagements', 'EvidenceRequest').objects.create(engagement=engagement, title='Preserved request', owner='Unexpected name')
    item = apps.get_model('inventory', 'InventoryItem').objects.create(customer=customer, kind='operation', name='Preserved operation', owner='')
    event = apps.get_model('inventory', 'InventoryEvent').objects.create(customer=customer, description='Preserved history', details={'before': {'owner':'Historical name'}})
    target = [('inventory', '0002_inventoryfollowup_notes_inventoryitem_notes_and_more')]
    try:
        MigrationExecutor(connection).migrate(target)
    except RuntimeError as exc:
        assert 'Unexpected text owners' in str(exc)
    else:
        raise AssertionError('Do not discard meaningful text owners silently')
    assert apps.get_model('engagements', 'EvidenceRequest').objects.get(pk=request.pk).owner == 'Unexpected name'
    apps.get_model('engagements', 'EvidenceRequest').objects.filter(pk=request.pk).update(owner='Unassigned')
    MigrationExecutor(connection).migrate(target)
    from engagements.models import Assessment, EvidenceRequest
    from inventory.models import InventoryItem, InventoryEvent
    assert EvidenceRequest.objects.get(pk=request.pk).owner_id is None
    assert InventoryItem.objects.get(pk=item.pk).owner_id is None
    assert InventoryItem.objects.get(pk=item.pk).notes == ''
    assert Assessment.objects.get(pk=assessment.pk).inventory_snapshot == frozen
    assert InventoryEvent.objects.get(pk=event.pk).details == {'before': {'owner':'Historical name'}}
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=os.getcwd(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
