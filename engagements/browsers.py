"""Screen-specific columns and filters using the shared read-only browser."""
from django.db.models import Case, CharField, F, Q, TextField, Value, When
from django.db.models.functions import Cast, Coalesce, Concat, NullIf, Replace
from library.record_browser import page_selection, query_url
from library.table_sorting import text_order, choice_order, owner_order
from django.db.models.fields.json import KeyTextTransform
from .models import APPLICABILITY, VERIFICATION, PRIORITY, CONFIDENCE, CONTACT_ROLES, EvidenceRequest


def text_search(queryset, query, fields):
    if not query:
        return queryset
    condition = Q()
    for field in fields:
        condition |= Q(**{field + '__icontains': query})
    return queryset.filter(condition)


def collection_browser(queryset, params, *, fields, columns, row_values, preview, ordering, fixed=None, controls=()):
    query = params.get('q', '').strip()[:200]
    filters = {**(fixed or {}), 'q': query}
    choices = []
    for name, label, options in controls:
        value = params.get(name, '')
        if value not in dict(options):
            value = ''
        filters[name] = value
        if value:
            queryset = queryset.filter(**{name: value})
        choices.append({'name': name, 'label': label, 'choices': options, 'value': value, 'all_label': 'All ' + {'Applicability':'applicability states', 'Verification':'verification states', 'Status':'statuses', 'Priority':'priorities'}.get(label, label.lower())})
    browser = page_selection(text_search(queryset, query, fields), params, filters, row_values=row_values, columns=columns, ordering=ordering)
    return {**browser, 'query': query, 'fixed_filters': fixed or {}, 'filter_controls': choices,
            'columns': columns, 'row_actions': 0, 'preview_template': preview}


def assessment_browser(assessment, params):
    return collection_browser(assessment.results.select_related('investigation_owner'), params,
        fields=['control_code', 'control_title', 'investigation_owner__first_name', 'investigation_owner__last_name', 'observation', 'guidance__action__instruction'],
        ordering=[[text_order(Concat('control_code', Value(' · '), 'control_title'))],
                  [text_order(KeyTextTransform('instruction', KeyTextTransform('action', 'guidance')))],
                  [choice_order('applicability', APPLICABILITY)], [choice_order('verification', VERIFICATION)],
                  [owner_order('investigation_owner')]],
        columns=['Action', 'Applicability', 'Verification', 'Owner'],
        row_values=lambda item: (f'{item.control_code} · {item.control_title}', [item.guidance.get('action', {}).get('instruction', ''), item.get_applicability_display(), item.get_verification_display(), item.investigation_owner or 'Unassigned']),
        controls=[('applicability', 'Applicability', APPLICABILITY), ('verification', 'Verification', VERIFICATION)],
        preview='engagements/browsers/action_preview.html')


def evidence_browser(engagement, params):
    tab = params.get('collection', 'requests')
    if tab not in ['requests', 'evidence', 'findings']:
        tab = 'requests'
    definitions = {
        'requests': (engagement.evidence_requests.select_related('owner').order_by('pk'), ['title', 'instructions', 'owner__first_name', 'owner__last_name'], ['Owner', 'Due', 'Status'],
                     lambda item: (item.title, [item.owner or 'Unassigned', item.due_date or 'Not scheduled', item.get_status_display()]),
                     [('status', 'Status', EvidenceRequest._meta.get_field('status').choices)]),
        'evidence': (engagement.evidence.order_by('-collected_on', '-pk'), ['title', 'notes', 'provenance'], ['Collected', 'Provenance', 'Attachment'],
                     lambda item: (item.title, [item.collected_on, item.provenance, 'Available' if item.file else 'None']), []),
        'findings': (engagement.findings.order_by('pk'), ['title', 'condition', 'business_consequence', 'recommendation'], ['Priority', 'Impact / likelihood', 'Confidence'],
                     lambda item: (item.title, [item.get_priority_display(), f'{item.impact or "Unknown"} / {item.likelihood or "Unknown"}', item.get_confidence_display()]),
                     [('priority', 'Priority', PRIORITY)]),
    }
    queryset, fields, columns, values, controls = definitions[tab]
    ordering = {
        'requests': [[text_order('title')], [owner_order('owner')], [F('due_date')],
                     [choice_order('status', EvidenceRequest._meta.get_field('status').choices)]],
        'evidence': [[text_order('title')], [F('collected_on')], [text_order('provenance')],
                     [text_order(Case(When(file='', then=Value('None')), default=Value('Available')))]],
        'findings': [[text_order('title')], [choice_order('priority', PRIORITY)],
                     [F('impact'), F('likelihood')], [choice_order('confidence', CONFIDENCE)]],
    }[tab]
    browser = collection_browser(queryset, params, ordering=ordering, fields=fields, columns=columns, row_values=values, controls=controls,
        fixed={'area': 'evidence', 'collection': tab}, preview='engagements/browsers/evidence_preview.html')
    tabs = [(key, label, definitions[key][0].count()) for key, label in [('requests', 'Evidence requests'), ('evidence', 'Evidence register'), ('findings', 'Findings')]]
    return {**browser, 'collection': tab, 'collection_title': dict((key, label) for key, label, count in tabs)[tab],
            'tabs': [{'key': key, 'label': label, 'count': count, 'url': query_url({'area': 'evidence', 'collection': key})} for key, label, count in tabs]}


def contact_browser(queryset, params, *, engagement=None, available=None):
    tab = params.get('collection', 'linked') if engagement else 'directory'
    if tab not in ['linked', 'available'] and engagement:
        tab = 'linked'
    linking = tab == 'available'
    linked = engagement is not None and not linking
    if linking:
        queryset = available
    # A related contact is visible through an assigned engagement without granting
    # management/reuse rights. Available records are supplied by the permissioned view.
    prefix = 'contact__' if linked else ''
    status = params.get('visibility', '')
    if status not in ['active', 'archived', 'inactive'] or (status == 'inactive' and not linked):
        status = ''
    if status == 'archived':
        queryset = queryset.filter(**{prefix + 'archived': True})
    elif status == 'active':
        queryset = queryset.filter(**{prefix + 'archived': False})
        if linked:
            queryset = queryset.filter(active=True)
    elif status == 'inactive':
        queryset = queryset.filter(active=False)
    queryset = queryset.annotate(browser_name=Concat(prefix + 'first_name', Value(' '), prefix + 'last_name'))
    fields = [prefix + name for name in ['first_name', 'last_name', 'organization', 'email', 'title']] + ['browser_name']

    def values(item):
        person = item.contact if linked else item
        state = 'Archived' if person.archived else ('Inactive' if linked and not item.active else 'Active')
        if linked and item.primary:
            state += ' · Primary'
        organization = (item.affiliation_override or person.organization) if linked else person.organization
        return str(person), [organization or 'Not provided', item.role_labels if linked else person.title or 'Not provided', state]

    organization = F(prefix + 'organization')
    roles = F(prefix + 'title')
    state = Case(When(**{prefix + 'archived': True}, then=Value('Archived')),
                 *([When(active=False, then=Value('Inactive'))] if linked else []),
                 default=Value('Active'), output_field=CharField())
    if linked:
        organization = Coalesce(NullIf('affiliation_override', Value('')), organization)
        # JSON list punctuation is common to all rows; substitute the configured
        # role labels in SQL without loading every linked contact into Python.
        roles = Cast('roles', TextField())
        for key, label in CONTACT_ROLES:
            roles = Replace(roles, Value('"' + key + '"'), Value('"' + label + '"'))
        state = Concat(state, Case(When(primary=True, then=Value(' · Primary')), default=Value('')))
    ordering = [[text_order('browser_name')], [text_order(organization, 'Not provided')],
                [text_order(roles, 'Not provided')], [text_order(state)]]
    fixed = {'collection': tab, 'visibility': status}
    browser = collection_browser(queryset.order_by(prefix + 'last_name', prefix + 'first_name', 'pk'), params, fields=fields, columns=['Organization', 'Roles' if linked else 'Title', 'Status'],
        row_values=values, ordering=ordering, fixed=fixed, preview='engagements/browsers/contact_preview.html')
    # Visibility combines linked-record and person state, so it is handled above.
    options = [('active', 'Active'), ('archived', 'Archived')]
    if linked:
        options.append(('inactive', 'Inactive links'))
    browser['filter_controls'] = [{'name': 'visibility', 'label': 'Visibility', 'choices': options, 'value': status, 'all_label': 'All retained records'}]
    browser['fixed_filters'] = {'collection': tab}
    selected = browser['selected']
    return {**browser, 'collection': tab, 'linked_view': linked, 'linking_view': linking,
            'person': selected.contact if selected and linked else selected,
            'contact_tabs': [{'key': key, 'label': label, 'url': query_url({'collection': key})} for key, label in [('linked', 'Linked contacts'), ('available', 'Available to link')]]}
