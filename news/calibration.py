"""Versioned empirical calibration with incident-grouped held-out evaluation."""
from collections import defaultdict
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, OuterRef, Subquery
from .models import (MatchFeedback, CalibrationVersion, MatchingConfiguration, MatchingConfigurationEvent)
from .matching import MATCH_POLICY, wilson
from .match_cache import digest


def current_labels():
    latest=MatchFeedback.objects.filter(proposal_id=OuterRef('proposal_id')).order_by('-pk').values('pk')[:1]
    return MatchFeedback.objects.annotate(latest_id=Subquery(latest)).filter(pk=F('latest_id')).select_related('assessment','correct_issue','proposal__result__run__revision')


def build_calibration(name,actor):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    if not name.strip():
        raise ValidationError('A calibration name is required.')
    bins=defaultdict(dict)
    ids=[]
    for label in current_labels().order_by('pk').iterator(chunk_size=100):
        assessment=label.assessment
        if (label.outcome not in ['match','new','irrelevant'] or assessment.evidence.get('policy')!=MATCH_POLICY or
            assessment.evidence.get('embedding_model')!=settings.NEWS_EMBEDDING_MODEL or not assessment.evidence.get('complete')):
            continue
        if label.outcome=='match' and label.correct_issue.discovered_at>assessment.created_at:
            continue  # An issue created after retrieval could not have been matched then.
        correct=(assessment.prediction=='match' and label.outcome=='match' and assessment.target_issue_id==label.correct_issue_id) or (assessment.prediction=='new' and label.outcome=='new')
        family=f'issue:{label.correct_issue_id}' if label.correct_issue_id else 'irrelevant:'+digest([label.proposal.result.run.revision.title,label.proposal.result.run.revision.text])
        # One vote per incident per bin. Repeated syndicated reports cannot inflate confidence.
        bins[assessment.bucket].setdefault(family,[]).append((label.pk,correct))
        ids.append(label.pk)
    metrics={}
    for bucket,families in bins.items():
        splits={'train':[],'heldout':[]}
        for family,observations in families.items():
            correct=all(item[1] for item in observations)
            split='heldout' if int(digest(['split-1',family])[:8],16)%3==0 else 'train'
            splits[split].append(correct)
        train,test=splits['train'],splits['heldout']
        confidence=min(wilson(sum(train),len(train)),wilson(sum(test),len(test)))
        eligible=len(train)>=30 and len(test)>=30 and confidence>=.90 and bucket.startswith(('match|','new|')) and bucket.endswith('complete=True')
        metrics[bucket]={'train_n':len(train),'train_correct':sum(train),'heldout_n':len(test),'heldout_correct':sum(test),
            'confidence':confidence,'eligible':eligible}
    return CalibrationVersion.objects.create(name=name.strip(),policy_version=MATCH_POLICY,label_ids=sorted(set(ids)),
        dataset_hash=digest(sorted(set(ids))),metrics={'embedding_model':settings.NEWS_EMBEDDING_MODEL,'buckets':metrics,
            'method':'minimum 95% Wilson lower bound on train and incident-held-out accuracy; 30 unique incidents per split minimum'},created_by=actor)


@transaction.atomic
def configure(*,actor,calibration,autonomous):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    config,_=MatchingConfiguration.objects.select_for_update().get_or_create(pk=1)
    if autonomous:
        if not calibration or calibration.policy_version!=MATCH_POLICY or calibration.metrics.get('embedding_model')!=settings.NEWS_EMBEDDING_MODEL:
            raise ValidationError('Choose a compatible calibration version.')
        if not any(row.get('eligible') for row in calibration.metrics.get('buckets',{}).values()):
            raise ValidationError('Calibration has no supported >=90% buckets with sufficient held-out incidents.')
        current=set(current_labels().filter(pk__in=calibration.label_ids).values_list('pk',flat=True))
        if current!=set(calibration.label_ids):
            raise ValidationError('Calibration labels have been corrected; build a new version.')
    config.active_calibration=calibration
    config.autonomous_enabled=autonomous
    config.updated_by=actor
    config.save()
    MatchingConfigurationEvent.objects.create(actor=actor,reason='Admin explicitly updated matching configuration.',
        snapshot={'active_calibration':calibration.pk if calibration else None,'autonomous_enabled':autonomous})
    return config
