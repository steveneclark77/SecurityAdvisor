"""Small read-only helpers; callers must supply an already authorized queryset."""
from urllib.parse import urlencode
from django.core.paginator import Paginator


def query_url(filters, **changes):
    return '?' + urlencode({key: value for key, value in {**filters, **changes}.items() if value != ''})


def page_selection(queryset, params, filters):
    page = Paginator(queryset, 50).get_page(params.get('page'))
    items = list(page.object_list)
    selected = next((item for item in items if str(item.pk) == params.get('selected')), None)
    if selected is None and items:
        selected = items[0]
    return {
        'page': page, 'selected': selected,
        'previous_url': query_url(filters, page=page.previous_page_number()) if page.has_previous() else '',
        'next_url': query_url(filters, page=page.next_page_number()) if page.has_next() else '',
        'records': [{'item': item, 'url': query_url(filters, selected=item.pk, page=page.number) + '#record-preview', 'selected': item == selected} for item in items],
    }
