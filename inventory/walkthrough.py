"""Atomic, additive synthetic inventory generation with retained historical identity."""
from django.core.exceptions import ValidationError
from django.db import transaction
from engagements.models import Customer
from engagements.ownership import owner_contacts
from .models import InventoryItem, InventoryConnection, InventoryFollowUp, InventoryEvent
from .services import require_customer, record_fields
from .walkthrough_data import ITEMS, CONNECTIONS, FOLLOWUPS

PROVENANCE = 'Synthetic Harbor Cafe walkthrough template v2; illustrative scenario, not customer confirmation or tested evidence.'


def normalized_name(value):
    return ' '.join(value.split()).casefold()


def tracked_records(events, records, record_type):
    by_id = {record.pk:record for record in records}
    tracked = {}
    for event in events:
        marker = event.details.get('walkthrough', {})
        # v1 operation events predate the explicit record-type marker.
        if marker.get('record_type', 'item') == record_type:
            record = by_id.get(event.details.get('after', {}).get('id'))
            if record:
                tracked[marker['key']] = record
    return tracked


def capture_created(customer, user, record, key, record_type):
    record.full_clean()
    record.save()
    InventoryEvent.objects.create(customer=customer,actor=user,
        description=f'Added synthetic Harbor Cafe {record_type}: record {record.pk}.',
        details={'before':{},'after':record_fields(record),
                 'walkthrough':{'key':key,'version':2,'record_type':record_type}})


@transaction.atomic
def prefill_inventory(customer, user, owner=None):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    require_customer(user, customer)
    if not customer.synthetic:
        raise ValidationError('Walkthrough examples are available only for synthetic customers.')
    if owner and not owner_contacts(customer_id=customer.pk).filter(pk=owner.pk).exists():
        raise ValidationError({'owner':'Choose an active contact linked within this customer.'})
    events = list(customer.inventory_events.filter(details__walkthrough__key__isnull=False))
    existing = list(customer.inventory_items.all())
    tracked = tracked_records(events, existing, 'item')
    resolved = {}
    counts = {key:0 for key in ['items_added','items_kept','connections_added','connections_kept','followups_added','followups_kept','skipped']}
    for example in ITEMS:
        item = tracked.get(example['key'])
        if item and item.kind != example['kind']:
            item = None
        names = {normalized_name(name) for name in [example['name'], *example['aliases']]}
        matches = [record for record in existing if record.kind == example['kind'] and normalized_name(record.name) in names]
        if item or matches:
            # Do not guess which of multiple manual records to connect.
            resolved[example['key']] = item or (matches[0] if len(matches) == 1 else None)
            counts['items_kept'] += 1
            continue
        fields = {'notes':'Synthetic example; supporting people and responsibilities need confirmation.', **{key:value for key,value in example.items() if key not in ['key','aliases']}}
        if example['kind'] == 'operation':
            fields = {'outage_tolerance':'Unknown; confirm tolerance against critical business deadlines.',
                      'acceptable_data_loss':'Unknown; confirm whether inputs and records can be reconstructed.',
                      'workaround':'Unknown; confirm an approved alternative and recovery procedure.', **fields}
        item = InventoryItem(customer=customer,owner=owner,state='unknown',criticality='unknown',impact=None,
            provenance=PROVENANCE,**fields)
        capture_created(customer,user,item,example['key'],'item')
        existing.append(item)
        resolved[example['key']] = item
        counts['items_added'] += 1

    existing_connections = list(customer.inventory_connections.all())
    tracked = tracked_records(events, existing_connections, 'connection')
    for key,source_key,relationship,target_key,details in CONNECTIONS:
        source, target = resolved[source_key], resolved[target_key]
        if key in tracked:
            counts['connections_kept'] += 1
        elif not source or not target or source.archived or target.archived:
            counts['skipped'] += 1
        elif any(link.source_id == source.pk and link.target_id == target.pk and link.relationship == relationship for link in existing_connections):
            counts['connections_kept'] += 1
        else:
            link = InventoryConnection(customer=customer,source=source,target=target,relationship=relationship,
                details=details,access_method='Unknown; confirm integration and access paths.',state='unknown',provenance=PROVENANCE)
            capture_created(customer,user,link,key,'connection')
            existing_connections.append(link)
            counts['connections_added'] += 1

    existing_followups = list(customer.inventory_followups.all())
    tracked = tracked_records(events, existing_followups, 'followup')
    for key,item_key,question in FOLLOWUPS:
        item = resolved[item_key]
        if key in tracked:
            counts['followups_kept'] += 1
        elif not item or item.archived:
            counts['skipped'] += 1
        elif any(followup.item_id == item.pk and normalized_name(followup.question) == normalized_name(question) for followup in existing_followups):
            counts['followups_kept'] += 1
        else:
            followup = InventoryFollowUp(customer=customer,item=item,owner=owner,question=question,status='open',
                notes='Synthetic walkthrough question; resolve only after confirming facts.')
            capture_created(customer,user,followup,key,'followup')
            existing_followups.append(followup)
            counts['followups_added'] += 1
    return counts
