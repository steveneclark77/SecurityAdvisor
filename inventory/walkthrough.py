"""Explicit synthetic Harbor Cafe examples; never overwrite customer-entered facts."""
from django.core.exceptions import ValidationError
from django.db import transaction
from engagements.models import Customer
from .models import InventoryItem, InventoryEvent
from .services import require_customer, record_fields

EXAMPLES = [
    {'key':'harbor-payroll', 'aliases':['Payroll'], 'name':'Biweekly payroll', 'operation_category':'back_office',
     'description':'Prepare, approve, and submit employee payroll through a payroll provider.',
     'notes':'A bookkeeper assists with preparation; the selected owner is accountable. Provider and backup approver need confirmation.',
     'schedule':'Every other Friday; provider submission cutoff and time zone need confirmation.',
     'critical_windows':'Payroll preparation and the provider submission cutoff.',
     'financial_impact':'Possible late-payment costs and additional processing effort; amounts unknown.',
     'availability_impact':'Employees may receive pay late.',
     'reputation_impact':'Loss of employee trust.',
     'other_impact':'Employee personal and banking information requires protection; handling responsibilities need confirmation.',
     'exposures':['employee_pii']},
    {'key':'harbor-payments', 'aliases':['Vendor/rent payments'], 'name':'Vendor and rent payments', 'operation_category':'back_office',
     'description':'Review, approve, and pay supplier invoices and monthly cafe rent.',
     'notes':'A bookkeeper prepares payments; the selected owner approves them. Confirm the backup approver and verification of banking-detail changes.',
     'schedule':'Rent due on the first of each month; supplier deadlines and bank cutoff time zones need confirmation.',
     'critical_windows':'Payment approval deadlines, bank processing cutoffs, and rent due dates.',
     'financial_impact':'Possible late fees, duplicate or fraudulent payments, or disrupted supplier service; amounts unknown.',
     'availability_impact':'Missed supplier payments could interrupt deliveries needed for cafe service.',
     'reputation_impact':'Damage to supplier or landlord relationships.',
     'other_impact':'Confirm access to banking details and payment records.'},
    {'key':'harbor-maintenance', 'aliases':['Device maintenance and recovery'], 'name':'Device maintenance and backup recovery', 'operation_category':'ktlo',
     'description':'Maintain business devices and essential services, apply updates, and recover operations and data after disruption.',
     'notes':'Confirm who administers devices, identity, backups, and connectivity, including external support and a backup contact. No safeguard is verified by this example.',
     'schedule':'Maintenance outside service hours where possible; actual patching and backup schedules need confirmation.',
     'critical_windows':'Before service begins, during critical payment/payroll windows, and following device or connectivity failures.',
     'financial_impact':'Possible lost sales, recovery costs, and staff rework; amounts unknown.',
     'availability_impact':'Device, identity, backup, or connectivity failures can interrupt customer-facing and back-office operations.',
     'reputation_impact':'Repeated outages or data loss may reduce customer and employee trust.',
     'other_impact':'Confirm recovery responsibilities and handling of employee and customer information.'},
]


def normalized_name(value):
    return ' '.join(value.split()).casefold()


@transaction.atomic
def prefill_operations(customer, user, owner=None):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    require_customer(user, customer)
    if not customer.synthetic:
        raise ValidationError('Walkthrough examples are available only for synthetic customers.')
    existing = list(customer.inventory_items.filter(kind='operation'))
    names = {normalized_name(item.name) for item in existing}
    existing_ids = {item.pk for item in existing}
    tracked = {event.details['walkthrough']['key'] for event in customer.inventory_events.filter(
        details__walkthrough__key__in=[example['key'] for example in EXAMPLES])
        if event.details.get('after', {}).get('id') in existing_ids}
    added, kept = [], []
    for example in EXAMPLES:
        if example['key'] in tracked or any(normalized_name(name) in names for name in [example['name'], *example['aliases']]):
            kept.append(example['name'])
            continue
        fields = {key:value for key,value in example.items() if key not in ['key','aliases']}
        item = InventoryItem(customer=customer, kind='operation', owner=owner,
            state='unknown', criticality='unknown', impact=None,
            provenance='Synthetic Harbor Cafe walkthrough template v1; illustrative scenario, not customer confirmation or tested evidence.',
            outage_tolerance='Unknown; confirm tolerance against critical business deadlines.',
            acceptable_data_loss='Unknown; confirm whether inputs and records can be reconstructed.',
            workaround='Unknown; confirm an approved alternative and recovery procedure.', **fields)
        item.full_clean()
        item.save()
        InventoryEvent.objects.create(customer=customer,actor=user,
            description=f'Added synthetic Harbor Cafe walkthrough operation: {item.name}.',
            details={'before':{},'after':record_fields(item),'walkthrough':{'key':example['key'],'version':1}})
        added.append(item.name)
    return added, kept
