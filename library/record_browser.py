"""Small read-only helpers; callers must supply an already authorized queryset."""
from urllib.parse import urlencode
from django.core.paginator import Paginator
from .table_sorting import natural_key, sort_token


def query_url(filters, **changes):
    return '?' + urlencode({key: value for key, value in {**filters, **changes}.items() if value != ''})


def page_selection(queryset, params, filters, *, row_values=None, columns=()):
    labels = ['Name', *columns]
    token = sort_token(params.get('sort', ''), len(labels)) if row_values else ''
    filters = {**filters, 'sort':token}
    values = {}
    if token:
        # Computed display columns (roles, state labels, combined quantity) share
        # one ordering rule. Sort the scoped result before pagination, never just
        # the current page and never turn a request parameter into an ORM field.
        queryset = list(queryset)
        for item in queryset:
            values[item.pk] = row_values(item)
        index = int(token.lstrip('-'))
        queryset.sort(key=lambda item:natural_key([values[item.pk][0], *values[item.pk][1]][index]), reverse=token.startswith('-'))
    page = Paginator(queryset, 50).get_page(params.get('page'))
    items = list(page.object_list)
    selected = next((item for item in items if str(item.pk) == params.get('selected')), None)
    if selected is None and items:
        selected = items[0]
    records = []
    for item in items:
        row = {'item':item, 'url':query_url(filters,selected=item.pk,page=page.number)+'#record-preview', 'selected':item == selected}
        if row_values:
            row['label'], row['cells'] = values[item.pk] if item.pk in values else row_values(item)
        records.append(row)
    headers = []
    for index, label in enumerate(labels):
        active = token != '' and int(token.lstrip('-')) == index
        descending = active and token.startswith('-')
        next_token = str(index) if descending or not active else '-' + str(index)
        headers.append({'label':label, 'url':query_url(filters,sort=next_token,page='',selected=''),
            'order':('descending' if descending else 'ascending') if active else 'none',
            'next_order':'ascending' if descending or not active else 'descending', 'active':active})
    return {
        'page':page,'selected':selected,'records':records,'sort':token,'sort_headers':headers,
        'previous_url':query_url(filters,page=page.previous_page_number()) if page.has_previous() else '',
        'next_url':query_url(filters,page=page.next_page_number()) if page.has_next() else '',
    }
