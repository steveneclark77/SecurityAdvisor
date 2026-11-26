from django.core.exceptions import ValidationError
from django.test import TestCase
from engagements.models import Customer
from .models import InventoryItem,InventoryConnection,InventoryFollowUp,InventoryEvent


class InventoryValidationTests(TestCase):
    def test_provenance_criticality_and_confirmation_requirements(self):
        customer=Customer.objects.create(name='Synthetic validation')
        item=InventoryItem(customer=customer,kind='operation',name='Synthetic ordering')
        for values in [{'criticality':'high','criticality_reason':''},{'exposures':['unsupported']}]:
            obj=InventoryItem(customer=customer,kind='operation',name='Synthetic',**values)
            with self.assertRaises(ValidationError): obj.clean()
        item.save()
        other=InventoryItem.objects.create(customer=customer,kind='provider',name='Synthetic provider')
        for values in [{'state':'reported'},{'state':'confirmed','provenance':'Synthetic interview'}]:
            link=InventoryConnection(customer=customer,source=item,target=other,relationship='uses',details='Synthetic dependency',**values)
            with self.assertRaises(ValidationError): link.clean()
        followup=InventoryFollowUp(customer=customer,question='Synthetic question',status='resolved')
        with self.assertRaises(ValidationError): followup.clean()
        event=InventoryEvent.objects.create(customer=customer,description='Synthetic immutable event')
        with self.assertRaises(ValidationError): event.save()
        with self.assertRaises(ValidationError): event.delete()
