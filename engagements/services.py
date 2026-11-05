import hashlib
import secrets
from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Assessment, ActionResult, AuditEvent, Invite, Reassessment, Report


def require_access(user, engagement):
    if not user.is_active or not user.is_staff or not engagement.customer.assigned_users.filter(pk=user.pk).exists():
        raise PermissionDenied('Customer assignment required.')


def audit(engagement, user, description, details=None):
    AuditEvent.objects.create(engagement=engagement, actor=user, description=description, details=details or {})


@transaction.atomic
def start_assessment(*, engagement, baseline, user, profile, modifiers, rationale):
    require_access(user, engagement)
    if not baseline.approved_at:
        raise ValidationError('Select an approved baseline.')
    if profile not in baseline.snapshot.get('profiles', []):
        raise ValidationError('Profile must exist in the captured baseline.')
    if not set(modifiers).issubset(baseline.snapshot.get('modifiers', [])):
        raise ValidationError('Modifiers must exist in the captured baseline.')
    if not engagement.assessment_authorization.strip() or not rationale.strip():
        raise ValidationError('Assessment authorization and applicability rationale are required.')
    controls = baseline.snapshot.get('controls', [])
    if not controls:
        raise ValidationError('The baseline contains no controls.')
    assessment = Assessment.objects.create(engagement=engagement, baseline=baseline, profile=profile, modifiers=modifiers, applicability_rationale=rationale, created_by=user)
    for control in controls:
        applicable = control.get('universal') or profile in control.get('profiles', []) or bool(set(modifiers) & set(control.get('modifiers', [])))
        actions = control.get('actions') or [dict(instruction='Detailed actions missing: investigate using the captured procedure.', applicability=control.get('applicability',''), verification=control.get('verification',''))]
        for action in actions:
            ActionResult.objects.create(assessment=assessment, control_code=control['code'], control_title=control['title'], guidance={'control':control, 'action':action}, investigation_owner=engagement.contact, applicability='applicable' if applicable else 'excluded', applicability_reason='Selected profile/modifier or universal baseline coverage.' if applicable else 'Not selected by the chosen profile or modifiers. Consultant must review this exclusion.')
    audit(engagement, user, f'Created assessment {assessment.pk} from baseline {baseline.version}.')
    return assessment


def issue_invite(*, engagement, user, purpose, evidence_request=None):
    require_access(user, engagement)
    if purpose not in ['intake','evidence']:
        raise ValidationError('Unsupported invitation purpose.')
    if purpose == 'evidence' and (not evidence_request or evidence_request.engagement_id != engagement.pk):
        raise ValidationError('Evidence request must belong to this engagement.')
    raw = secrets.token_urlsafe(32)
    invite = Invite.objects.create(engagement=engagement, purpose=purpose, request=evidence_request, token_digest=hashlib.sha256(raw.encode()).hexdigest(), expires_at=timezone.now()+timedelta(days=7))
    audit(engagement, user, f'Issued a seven-day {purpose} invitation {invite.pk}.')
    return raw


def recommend_profile(answers):
    industry = answers.get('industry')
    return {'profile': industry or 'Other professional and consulting services', 'modifiers':answers.get('modifiers', []), 'reason': 'Suggested from the customer-selected business activity and technology exposures. This is a starting fit, not an exact classification; confirm with the customer and record overrides.' if industry else 'Industry is unknown. Generic professional services is a provisional fallback requiring consultant review.', 'confidence':'provisional'}


def flag_reassessments(baseline):
    """Conservative matching on changed guidance and captured customer applicability."""
    for assessment in Assessment.objects.exclude(baseline=baseline).select_related('baseline'):
        # Do not flag a later assessment when reviewing an older version.
        if assessment.baseline.created_at >= baseline.created_at:
            continue
        old = {c['code']:c for c in assessment.baseline.snapshot.get('controls', [])}
        changed = []
        for control in baseline.snapshot.get('controls', []):
            prior = old.get(control['code'])
            relevant = lambda c: c and (c.get('universal') or assessment.profile in c.get('profiles', []) or bool(set(assessment.modifiers) & set(c.get('modifiers', []))))
            if control != prior and (relevant(control) or relevant(prior)):
                changed.append(control['code'])
        removed = [code for code,control in old.items() if code not in {c['code'] for c in baseline.snapshot.get('controls', [])} and (control.get('universal') or assessment.profile in control.get('profiles',[]) or set(assessment.modifiers) & set(control.get('modifiers',[])))]
        if changed or removed:
            Reassessment.objects.get_or_create(assessment=assessment, baseline=baseline, defaults={'reason':f'Changed/new relevant controls: {", ".join(changed) or "none"}. Removed relevant controls: {", ".join(removed) or "none"}. Matching uses profile/modifiers, not confirmed asset detection; review applicability.'})


@transaction.atomic
def capture_report(*, engagement, user):
    require_access(user, engagement)
    findings = []
    for finding in engagement.findings.prefetch_related('actions','evidence','tasks__retests__evidence','tasks__dependencies'):
        details = {field.name:getattr(finding,field.name) for field in finding._meta.fields if field.name not in ['id','engagement','assessment']}
        details['id'] = finding.pk
        details['baseline'] = finding.assessment.baseline.version
        details['assessment_id'] = finding.assessment_id
        details['actions'] = [dict(id=a.pk, control=a.control_code, instruction=a.guidance['action']['instruction'], implementation=a.implementation, verification=a.verification) for a in finding.actions.all()]
        details['evidence_ids'] = list(finding.evidence.values_list('pk',flat=True))
        details['tasks'] = []
        for task in finding.tasks.all():
            data = {field.name:getattr(task,field.name) for field in task._meta.fields if field.name not in ['finding']}
            data['dependencies'] = list(task.dependencies.values_list('pk',flat=True))
            data['retests'] = [dict(tested_on=r.tested_on.isoformat(), tester=r.tester.get_username(), outcome=r.outcome, procedure_and_result=r.procedure_and_result, residual_risk=r.residual_risk, evidence_ids=list(r.evidence.values_list('pk',flat=True))) for r in task.retests.all()]
            data = {k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in data.items()}
            details['tasks'].append(data)
        details = {k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in details.items()}
        findings.append(details)
    results = []
    for assessment in engagement.assessments.select_related('baseline'):
        for result in assessment.results.prefetch_related('evidence'):
            results.append(dict(id=result.pk, assessment_id=assessment.pk, baseline=assessment.baseline.version, control=result.control_code, title=result.control_title, guidance=result.guidance, applicability=result.applicability, reason=result.applicability_reason, implementation=result.implementation, verification=result.verification, confidence=result.confidence, observation=result.observation, investigation_owner=result.investigation_owner, followup_due=result.followup_due.isoformat() if result.followup_due else None, evidence_ids=list(result.evidence.values_list('pk',flat=True)), verified_at=result.verified_at.isoformat() if result.verified_at else None))
    snapshot = {
        'customer':engagement.customer.name, 'synthetic':engagement.customer.synthetic, 'engagement':engagement.title,
        'scope':engagement.scope, 'exclusions':engagement.exclusions, 'assessment_authorization':engagement.assessment_authorization,
        'business_context':{f:getattr(engagement,f) for f in ['financial_thresholds','outage_tolerance','critical_operations','reputation_context']},
        'scoring_policy':'Impact and likelihood use 1–5 ratings. Priority is documented consultant judgment; no automatic matrix has been approved. Missing information is unknown, not low risk.',
        'limitations':'Development report using synthetic data. Guidance is incomplete and not a certification. Review finding-specific limitations, unknowns, untested actions, and exclusions.',
        'baselines':[dict(version=a.baseline.version, coverage_gaps=a.baseline.coverage_gaps, profile=a.profile, modifiers=a.modifiers, rationale=a.applicability_rationale) for a in engagement.assessments.select_related('baseline')],
        'findings':sorted(findings, key=lambda f: {'critical':0,'high':1,'medium':2,'low':3,'unrated':4}[f['priority']]), 'results':results,
        'evidence':[dict(id=e.pk,title=e.title,notes=e.notes,provenance=e.provenance,collected_on=e.collected_on.isoformat(),has_attachment=bool(e.file)) for e in engagement.evidence.all()],
        'next_review':engagement.next_review.isoformat() if engagement.next_review else 'Not scheduled', 'review_triggers':engagement.review_triggers,
    }
    report = Report.objects.create(engagement=engagement, created_by=user, snapshot=snapshot)
    audit(engagement, user, f'Generated preserved report {report.pk}.')
    return report
