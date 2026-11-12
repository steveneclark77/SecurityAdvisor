"""Read-only, record-derived workflow guidance. No completion or risk decisions."""
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from .models import ActionResult, Remediation


LABELS = {'recorded': 'Recorded', 'progress': 'In progress', 'new': 'Not started'}


def engagement_journey(engagement, intake):
    contacts = engagement.active_contacts.count()
    scope_ready = bool(contacts and engagement.scope.strip() and engagement.assessment_authorization.strip())
    inventory = engagement.customer.inventory_items.filter(archived=False)
    items = inventory.count()
    operations = inventory.filter(kind='operation').exists()
    unknown = inventory.filter(state='unknown').count()
    gaps = engagement.customer.inventory_followups.filter(status='open').count()
    assessments = engagement.assessments.count()
    outstanding = ActionResult.objects.filter(assessment__engagement=engagement).exclude(applicability='excluded').filter(Q(applicability='unknown') | Q(verification__in=['not_tested', 'inconclusive'])).count()
    requests = engagement.evidence_requests.count()
    pending = engagement.evidence_requests.exclude(status='reviewed').count()
    evidence = engagement.evidence.count()
    findings = engagement.findings.count()
    unplanned_findings = engagement.findings.filter(tasks__isnull=True, risk_acceptance='').count()
    tasks = Remediation.objects.filter(finding__engagement=engagement)
    task_count = tasks.count()
    unverified = tasks.exclude(status='verified').count()
    reports = engagement.reports.count()
    intake_links = engagement.invite_set.filter(purpose='intake')
    invited = intake_links.filter(used_at__isnull=True, expires_at__gt=timezone.now()).exists()
    intake_started = invited or intake_links.exists()
    base = reverse('engagement_detail', args=[engagement.pk])

    def count_text(number, noun):
        return f'{number} {noun}' + ('' if number == 1 else 's')

    def step(key, title, state, detail, href, *, action=None, reason, bullets):
        return {'key': key, 'title': title, 'state': state, 'status': LABELS[state], 'detail': detail,
                'href': href, 'action': action or ('Start' if state == 'new' else 'Edit'),
                'reason': reason, 'bullets': bullets}

    steps = [
        step('scope', 'Scope and contacts', 'recorded' if scope_ready else 'progress', f'{count_text(contacts, "active contact")} · scope recorded',
             base+'?area=scope#work-scope',
             reason='Review scope, assessment authority, business context, and the people involved before collecting or interpreting evidence.', bullets=['Scope and exclusions', 'Assessment and change authority', 'Active contacts and business impact context']),
        step('intake', 'Customer intake', 'recorded' if intake else ('progress' if intake_started else 'new'),
             'Customer response received' if intake else ('Submission link issued; awaiting response' if invited else ('Previous link closed; no response recorded' if intake_started else 'No customer response recorded')), base+'?area=intake#work-intake', action='Review' if intake else ('Edit' if intake_started else 'Start'),
             reason='Review the customer response and confirm unclear facts. Intake is optional for a consultant-led engagement.', bullets=['Business activities and technology', 'Operational deadlines and impact', 'Information to confirm with the customer']),
        step('inventory', 'Inventory and operations', ('progress' if unknown or gaps or not operations else 'recorded') if items else 'new', f'{count_text(items, "active record")} · {unknown} unknown · {count_text(gaps, "open follow-up")}', reverse('inventory_detail', args=[engagement.customer_id]),
             reason='Record business operations and their dependencies before starting an assessment. The assessment captures inventory as it stands at that time.', bullets=['Business operations, owners, and deadlines', 'Providers, devices, software, and networks', 'Data and dependencies', 'Missing facts under Information to confirm']),
        step('assessments', 'Assessments', ('progress' if outstanding else 'recorded') if assessments else 'new', f'{count_text(assessments, "assessment")} · {count_text(outstanding, "action")} needing investigation', base+'?area=assessments#work-assessments' if assessments else reverse('assessment_new', args=[engagement.pk]),
             reason='Choose an approved baseline and review applicability, observations, and verification. Unknown results remain investigation work.', bullets=['Approved baseline and profile', 'Captured inventory and applicability', 'Evidence-backed observations and uncertainty']),
        step('evidence', 'Evidence and findings', ('progress' if pending or outstanding else 'recorded') if requests or evidence or findings else 'new', f'{count_text(evidence, "evidence item")} · {count_text(findings, "finding")} · {count_text(pending, "open request")}', base+'?area=evidence#work-evidence',
             reason='Collect and review evidence, investigate uncertainties, and document findings when warranted. A missing finding is not proof that the customer is secure.', bullets=['Evidence requests and provenance', 'Review submitted material', 'Findings, business consequences, and uncertainty']),
        step('remediation', 'Remediation and retesting', ('progress' if unverified or unplanned_findings else 'recorded') if task_count else 'new', f'{count_text(task_count, "task")} · {unverified} not verified · {count_text(unplanned_findings, "unplanned finding")}', base+'?area=remediation#work-remediation',
             reason='Plan improvements for findings, obtain separate change authority, and retest implemented work before recording verification.', bullets=['Owners, dependencies, and change authorization', 'Implementation and recovery arrangements', 'Retest evidence and residual risk']),
        step('reports', 'Reports', 'recorded' if reports else 'new', count_text(reports, 'preserved report'), base+'?area=reports#work-reports',
             reason='Capture a point-in-time report with findings, evidence, unknowns, and limitations. Reports can be produced before remediation is complete.', bullets=['Executive and technical views', 'Uncertainty, exclusions, and limitations', 'Follow-up dates and review triggers']),
    ]
    if not scope_ready:
        next_key = 'scope'
    elif not intake and not invited and not items and not assessments:
        next_key = 'intake'
    elif not items or not operations:
        next_key = 'inventory'
    elif not assessments:
        next_key = 'assessments'
    elif unplanned_findings or unverified:
        next_key = 'remediation'
    elif outstanding or pending or not evidence:
        next_key = 'evidence'
    else:
        next_key = 'reports'
    for item in steps:
        item['recommended'] = item['key'] == next_key
    return {'phases': [
        {'title': 'Understand the business', 'steps': steps[:3]},
        {'title': 'Assess and investigate', 'steps': steps[3:5]},
        {'title': 'Improve and report', 'steps': steps[5:]},
    ], 'next': next(item for item in steps if item['recommended']), 'open_information': gaps, 'assessment_count': assessments}
