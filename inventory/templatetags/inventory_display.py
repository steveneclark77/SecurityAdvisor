from django import template
from inventory.models import InventoryItem, EXPOSURES

register=template.Library()


@register.filter
def inventory_fields(record):
    rows=[]
    for key,value in record.items():
        if key in ['id','customer','updated_at'] or value in ['',None,[]]:
            continue
        if key == 'owner_contact':
            continue
        field=InventoryItem._meta.get_field(key)
        if key=='exposures':
            value=', '.join(dict(EXPOSURES).get(v,v) for v in value)
        elif field.choices:
            value=dict(field.choices).get(value,value)
        elif isinstance(value,bool):
            value='Yes' if value else 'No'
        rows.append((field.verbose_name.capitalize(),value))
    return rows
