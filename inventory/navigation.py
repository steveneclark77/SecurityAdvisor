"""Inventory form navigation always stays inside the authorized customer list."""
from urllib.parse import urlencode, urlsplit
from django.urls import reverse
from .models import InventoryItem, InventoryConnection


def list_url(customer, obj):
    if isinstance(obj, InventoryItem):
        params = {'kind': obj.kind}
        if obj.pk:
            params['selected'] = obj.pk
    else:
        params = {'area': 'relationships' if isinstance(obj, InventoryConnection) else 'followups'}
    if getattr(obj, 'archived', False):
        params['archived'] = 'yes'
    return reverse('inventory_detail', args=[customer.pk]) + '?' + urlencode(params)


def cancel_url(customer, obj, candidate):
    fallback = list_url(customer, obj)
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return fallback
    if parsed.scheme or parsed.netloc or parsed.path != reverse('inventory_detail', args=[customer.pk]):
        return fallback
    return candidate
