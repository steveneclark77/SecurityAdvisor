"""Read-only, customer-scoped inventory explorer navigation."""
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Count, Q
from .models import ITEM_KINDS, FACT_STATES
from . import services
from .templatetags.inventory_display import inventory_fields

CATEGORIES = [('operation', 'Operations'), ('provider', 'Providers'), ('device', 'Devices'),
              ('software', 'Software'), ('network', 'Networks'), ('physical', 'Physical systems'), ('data', 'Data')]


def explorer_context(customer, params):
    kind = params.get('kind', '')
    if kind not in dict(ITEM_KINDS):
        kind = ''
    area = params.get('area', 'records')
    if area not in ['records', 'relationships', 'followups', 'history']:
        area = 'records'
    state = params.get('state', '')
    if state not in dict(FACT_STATES):
        state = ''
    query = params.get('q', '').strip()[:200]
    archived = params.get('archived') == 'yes'
    base = customer.inventory_items.all()
    if not archived:
        base = base.filter(archived=False)
    counts = dict(base.values('kind').annotate(total=Count('pk')).values_list('kind', 'total'))
    filters = {'kind': kind, 'q': query, 'state': state, 'archived': 'yes' if archived else ''}

    def url(**changes):
        return '?' + urlencode({k: v for k, v in {**filters, **changes}.items() if v != ''})

    items = base
    if kind:
        items = items.filter(kind=kind)
    if state:
        items = items.filter(state=state)
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(owner__icontains=query) | Q(vendor_product__icontains=query))
    page = Paginator(items, 50).get_page(params.get('page'))
    visible = list(page.object_list)
    selected = next((item for item in visible if str(item.pk) == params.get('selected')), None)
    if selected is None and visible:
        selected = visible[0]
    connections = customer.inventory_connections.select_related('source', 'target')
    if not archived:
        connections = connections.filter(archived=False)
    followups = customer.inventory_followups.select_related('item', 'source_intake')
    return {
        'area': area, 'kind': kind, 'query': query, 'state': state, 'archived': archived,
        'states': FACT_STATES, 'page': page,
        'previous_url': url(page=page.previous_page_number()) if page.has_previous() else '',
        'next_url': url(page=page.next_page_number()) if page.has_next() else '',
        'categories': [{'key': key, 'label': label, 'count': counts.get(key, 0), 'url': url(kind=key)} for key, label in CATEGORIES],
        'all_count': sum(counts.values()), 'all_url': url(kind=''),
        'collections': [{'key': key, 'label': label, 'url': url(area=key)} for key, label in [('relationships', 'Relationships'), ('followups', 'Information to confirm'), ('history', 'History')]],
        'heading': dict(CATEGORIES).get(kind, 'All records'),
        'add_label': 'Add ' + dict(ITEM_KINDS).get(kind, 'record').lower(),
        'records': [{'item': item, 'url': url(selected=item.pk, page=page.number), 'selected': item == selected} for item in visible],
        # Retain the existing context shape for callers testing active-record scope.
        'rows': [(item, inventory_fields(services.record_fields(item))) for item in visible],
        'selected': selected,
        'selected_fields': inventory_fields(services.record_fields(selected)) if selected else [],
        'selected_connections': connections.filter(Q(source=selected) | Q(target=selected)) if selected else [],
        'selected_followups': followups.filter(item=selected, status='open') if selected else [],
        'connections': connections, 'followups': followups,
        'history': customer.inventory_events.all(), 'kinds': ITEM_KINDS,
    }
