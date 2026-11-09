from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from engagements.models import Customer
from .models import InventoryItem, InventoryConnection, InventoryFollowUp, InventoryEvent


def require_customer(user,customer):
    if not user.is_active or not user.is_staff or not customer.assigned_users.filter(pk=user.pk).exists():
        raise PermissionDenied('Customer assignment required.')


def record_fields(obj):
    data = {}
    for field in obj._meta.fields:
        value = getattr(obj,field.attname)
        data[field.name] = value.isoformat() if hasattr(value,'isoformat') else value
    return data


@transaction.atomic
def capture_inventory(customer):
    # Writers use the same customer lock: application changes cannot interleave
    # the item and connection reads of this historical snapshot.
    Customer.objects.select_for_update().get(pk=customer.pk)
    return {'captured_at':timezone.now().isoformat(),'items':[record_fields(x) for x in InventoryItem.objects.filter(customer=customer)],'connections':[{**record_fields(x),'source_name':x.source.name,'target_name':x.target.name,'relationship_label':x.get_relationship_display()} for x in InventoryConnection.objects.filter(customer=customer).select_related('source','target')],'followups':[record_fields(x) for x in InventoryFollowUp.objects.filter(customer=customer)]}


def intake_followup(intake,user=None):
    facts = str(intake.answers.get('unknowns','')).strip()
    if not facts:
        return None
    customer = intake.engagement.customer
    with transaction.atomic():
        Customer.objects.select_for_update().get(pk=customer.pk)
        followup,created = InventoryFollowUp.objects.get_or_create(source_intake=intake,defaults={'customer':customer,'question':facts})
        if created:
            InventoryEvent.objects.create(customer=customer,actor=user,description=f'Created information follow-up from intake {intake.pk}.')
    return followup


EXPOSURE_MODIFIERS = {'payments':'Payment processing','software_development':'Software development','public_apps':'Public applications','remote_access':'Remote workers','ot':'Operational technology'}


def scope_guidance(customer):
    active=InventoryItem.objects.filter(customer=customer,archived=False)
    exposures={e for item in active for e in item.exposures}
    return {'operation_names':[x.name for x in active if x.kind=='operation'], 'suggested_modifiers':sorted({EXPOSURE_MODIFIERS[e] for e in exposures if e in EXPOSURE_MODIFIERS}), 'unresolved':customer.inventory_followups.filter(status='open').count()}
