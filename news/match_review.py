"""Append-only human feedback and guarded autonomous link/new-issue actions."""
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from .access import require_reviewer
from .models import (MatchingConfiguration, MatchingConfigurationEvent, MatchDecision, MatchFeedback,
                     MatchAssessment, Issue, IssueArticleLink, IssueProposal, InboxEvent, Source, MatchQueue)
from .match_cache import refresh_profile
from .versioning import create_version


def notify(kind,proposal,issue=None,decision=None):
    title=Issue.objects.select_related('current_version').get(pk=issue.pk).name if issue and kind=='new' else proposal.content.get('name','Security news')
    return InboxEvent.objects.get_or_create(key=f'{kind}:{decision.pk if decision else proposal.pk}',defaults={
        'kind':kind,'proposal':proposal,'issue':issue,'decision':decision,'title':title[:500]})[0]


def save_feedback(decision,actor,config=None):
    label=MatchFeedback.objects.create(proposal=decision.proposal,assessment=decision.assessment,decision=decision,
        outcome=decision.outcome,correct_issue=decision.issue,actor=actor,rationale=decision.rationale)
    config=config or MatchingConfiguration.objects.select_for_update().get(pk=1)
    calibration=config.active_calibration
    if calibration and MatchFeedback.objects.filter(proposal=decision.proposal,pk__in=calibration.label_ids).exists():
        config.autonomous_enabled=False
        config.save(update_fields=['autonomous_enabled','updated_at'])
        MatchingConfigurationEvent.objects.create(actor=actor,reason='A consumed calibration example was corrected; autonomy paused pending recalibration.',
            snapshot={'autonomous_enabled':False,'active_calibration':calibration.pk})
    return label


@transaction.atomic
def act(assessment, *, outcome, actor=None, target_issue_id=None, rationale='', content=None, expected_decision_id=None, expected_identity=None, automatic=False):
    from .matching import MATCH_POLICY
    from django.conf import settings
    from .analysis import validate_new_issue
    if not automatic:
        require_reviewer(actor)
        permissions=['news.add_matchfeedback']
        if outcome in ['match','new']:
            permissions += ['news.add_issuearticlelink','news.change_issue']
        if outcome=='new':
            permissions += ['news.add_issue','news.add_issueversion']
        if not actor.has_perms(permissions):
            raise PermissionDenied
    if outcome not in ['match','new','irrelevant','uncertain'] or not rationale.strip():
        raise ValidationError('Select a decision and explain its rationale.')
    Source.objects.select_for_update().order_by('pk').first()
    proposal=IssueProposal.objects.select_for_update().select_related('result__run__revision__article').get(pk=assessment.proposal_id)
    assessment=MatchAssessment.objects.get(pk=assessment.pk,proposal=proposal)
    previous=proposal.match_decisions.order_by('-pk').first()
    if previous and automatic:
        return previous
    if (previous.pk if previous else None)!=expected_decision_id and not automatic:
        raise ValidationError('Another reviewer changed this decision. Reload before saving.')
    target=None
    original_new=proposal.match_decisions.filter(outcome='new',issue__isnull=False).order_by('pk').first()
    issue_ids=sorted(set([pk for pk in [target_issue_id,previous.issue_id if previous else None,original_new.issue_id if original_new else None] if pk]))
    issues={issue.pk:issue for issue in Issue.objects.select_for_update().filter(pk__in=issue_ids).order_by('pk')}
    if outcome=='match':
        target=issues.get(target_issue_id)
        if not target or not target.current_version_id:
            raise ValidationError('Choose an existing issue.')
    if target and not automatic and expected_identity is not None:
        if refresh_profile(target.pk).identity_hash!=expected_identity:
            raise ValidationError('The issue identity changed. Reload before reviewing.')
    config=MatchingConfiguration.objects.select_for_update().get(pk=1)
    if automatic:
        calibration=config.active_calibration
        if (not config.autonomous_enabled or not calibration or assessment.calibration_id!=calibration.pk or
            assessment.catalog_generation!=config.catalog_generation or calibration.policy_version!=MATCH_POLICY or
            calibration.metrics.get('embedding_model')!=settings.NEWS_EMBEDDING_MODEL or
            assessment.evidence.get('embedding_model')!=settings.NEWS_EMBEDDING_MODEL or
            assessment.prediction!=outcome or assessment.confidence is None or assessment.confidence<.90 or
            not assessment.evidence.get('complete') or assessment.evidence.get('candidate_limit_hit')):
            return None
        if outcome=='match':
            profile=refresh_profile(target.pk)
            evidence=next((item for item in assessment.evidence['comparisons'] if item['issue_id']==target.pk),None)
            if not evidence or profile.identity_hash!=evidence['identity_hash']:
                return None
    revision=proposal.result.run.revision
    created_new=False
    if outcome=='new' and original_new:
        target=issues[original_new.issue_id]
    elif outcome=='new':
        created_new=True
        values={**proposal.content,**(content or {})}
        if set(values)-{'name','description','kind','severity','identifiers','remediation'}:
            raise ValidationError('Unexpected issue fields.')
        validate_new_issue(values.get('identifiers',''))
        target=Issue.objects.create(source=revision.article.source,first_scan=revision.article.first_scan,
            identity=f'match-proposal-{proposal.pk}',last_seen_at=timezone.now())
        values.update(url=revision.article.url,published_at=revision.published_at)
        create_version(issue=target,expected_version_id=None,content=values,actor=actor,
            origin='automated_proposal' if automatic else 'consultant_edit',change_reason=rationale,
            references=[{'source_id':revision.article.source_id,'source_name':revision.source_name,
                'source_website':revision.source_website,'source_url':revision.article.url,
                'source_published_at':revision.published_at,'notes':'New incident; unreviewed defaults.' if automatic else 'Human confirmed new incident.'}])
        refresh_profile(target.pk,products=proposal.matching.get('affected_products',[]),versions=proposal.matching.get('affected_versions',[]))
    if previous and previous.issue_id and previous.issue_id!=(target.pk if target else None):
        IssueArticleLink.objects.create(issue_id=previous.issue_id,revision=revision,relationship='retracts',actor=actor,
            rationale='Corrected matching decision: '+rationale)
    if target:
        IssueArticleLink.objects.create(issue=target,revision=revision,relationship='supports',actor=actor,
            rationale=('Automatic duplicate-source link: ' if automatic and outcome=='match' else '')+rationale)
    decision=MatchDecision.objects.create(proposal=proposal,assessment=assessment,outcome=outcome,issue=target,
        automatic=automatic,actor=actor,rationale=rationale)
    if not automatic:
        save_feedback(decision,actor,config)
    MatchQueue.objects.filter(proposal=proposal).update(status='waiting' if outcome=='uncertain' else 'resolved',last_processed_at=timezone.now())
    if created_new:
        notify('new',proposal,target,decision)
    elif automatic and outcome=='match':
        notify('automatic_link',proposal,target,decision)
    return decision


def apply_automatic(assessment):
    if assessment.prediction not in ['match','new']:
        return None
    return act(assessment,outcome=assessment.prediction,target_issue_id=assessment.target_issue_id,
        automatic=True,rationale='Calibrated confidence >=90%; no existing issue content changed for duplicate links.')


def record_content_review(content_decision, target_issue_id):
    """Accepted content reviews also explicitly identify an existing/new incident.

    Rejecting a content recommendation is not a negative identity label.
    """
    from .access import is_reviewer
    if content_decision.decision!='accept' or not is_reviewer(content_decision.actor):
        return
    proposal=content_decision.proposal
    assessment=proposal.assessments.order_by('-pk').first()
    if not assessment:
        from .matching import assess
        assessment=assess(proposal)
    issue=content_decision.issue_version.issue
    previous=proposal.match_decisions.order_by('-pk').first()
    if previous and previous.issue_id and previous.issue_id!=issue.pk:
        IssueArticleLink.objects.create(issue_id=previous.issue_id,revision=proposal.result.run.revision,
            relationship='retracts',actor=content_decision.actor,rationale='Content review corrected incident association.')
    outcome='match' if target_issue_id else 'new'
    decision=MatchDecision.objects.create(proposal=proposal,assessment=assessment,outcome=outcome,issue=issue,
        automatic=False,actor=content_decision.actor,rationale=content_decision.rationale)
    save_feedback(decision,content_decision.actor)
    MatchQueue.objects.filter(proposal=proposal).update(status='resolved',last_processed_at=timezone.now())
    if outcome=='new':
        refresh_profile(issue.pk,products=proposal.matching.get('affected_products',[]),versions=proposal.matching.get('affected_versions',[]))
        notify('new',proposal,issue,decision)
