"""Cached candidate comparisons and conservative calibrated routing."""
import math
import re
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from .models import (Issue, IssueMatchProfile, MatchingConfiguration, MatchComparison,
                     MatchAssessment, IssueProposal, MatchDecision, IssueMatchKey, MatchQueue)
from .match_cache import (POLICY_VERSION, digest, extraction_data, summary, get_embedding,
                         refresh_profile, bucket_keys)

MATCH_POLICY='matching-1'
CANDIDATE_LIMIT=200


def overlap(left,right):
    a,b=set(left),set(right)
    return len(a&b)/len(a|b) if a and b else 0.0


def cosine(left,right):
    return max(-1.0,min(1.0,sum(a*b for a,b in zip(left,right,strict=True))))


def comparison(proposal_data,embedding,profile):
    key=digest([MATCH_POLICY,digest(proposal_data),profile.issue_id,profile.identity_hash,
                embedding.key if embedding else None,profile.embedding.key if profile.embedding_id else None])
    existing=MatchComparison.objects.filter(key=key).first()
    if existing:
        return existing
    left,right=proposal_data,profile.fingerprint
    exact=bool(set(left['identifiers'])&set(right['identifiers']))
    conflict=bool(left['identifiers'] and right['identifiers'] and not exact)
    products=overlap(left['products'],right['products'])
    semantic=cosine(embedding.vector,profile.embedding.vector) if embedding and profile.embedding_id else None
    lexical=overlap(left['name'].casefold().split(),right['name'].casefold().split())
    # A disjoint product list is a blocker even if an identifier overlaps.
    product_conflict=bool(left['products'] and right['products'] and not products)
    blocked=conflict or product_conflict
    score=0 if blocked else 1.0 if exact else max(0,semantic or 0)*.8+lexical*.15+products*.05
    features={'source_version_id':profile.source_version_id,'identity_fields':{key:right[key] for key in ['identifiers','products','versions','kind']},'exact':exact,'identifier_conflict':conflict,'product_conflict':product_conflict,
              'products':products,'semantic':semantic,'lexical':lexical,'score':score,
              'version_overlap':overlap(left['versions'],right['versions']),
              'complete':bool(embedding and profile.embedding_id),'blocked':blocked}
    return MatchComparison.objects.get_or_create(key=key,defaults={'issue':profile.issue,'extraction_hash':digest(left),
        'identity_hash':profile.identity_hash,'policy_version':MATCH_POLICY,'features':features})[0]


def profile_is_current(profile):
    return profile.source_version_id==profile.issue.current_version_id


def assess(proposal):
    config,_=MatchingConfiguration.objects.get_or_create(pk=1)
    data=extraction_data(proposal)
    embedded=get_embedding(summary(data))
    identifiers=data['identifiers']
    tokens={word[:200] for word in re.findall(r'[a-z0-9]{4,}',data['name'].lower())}
    keys=IssueMatchKey.objects.filter(Q(kind='identifier',value__in=identifiers)|
        Q(kind='product',value__in=data['products'])|Q(kind='token',value__in=tokens))
    condition=Q(pk__in=keys.values('profile_id'))
    if embedded:
        condition |= Q(embedding__buckets__key__in=bucket_keys(embedded.vector))
    candidates=list(IssueMatchProfile.objects.filter(condition).select_related('issue','embedding').distinct().order_by('pk')[:CANDIDATE_LIMIT+1])
    complete=embedded is not None and len(candidates)<=CANDIDATE_LIMIT
    # No claims of completeness when any current issue has not been indexed.
    indexed=config.index_ready_generation==config.catalog_generation and config.index_ready_model==settings.NEWS_EMBEDDING_MODEL
    missing=False if indexed else Issue.objects.filter(current_version__isnull=False).exclude(
        pk__in=IssueMatchProfile.objects.filter(source_version_id=F('issue__current_version_id'),
            embedding__model=settings.NEWS_EMBEDDING_MODEL).values('issue_id')).exists()
    if not missing and not indexed:
        MatchingConfiguration.objects.filter(pk=1,catalog_generation=config.catalog_generation).update(
            index_ready_generation=config.catalog_generation,index_ready_model=settings.NEWS_EMBEDDING_MODEL)
    complete=complete and not missing
    valid=[profile for profile in candidates[:CANDIDATE_LIMIT] if profile_is_current(profile)]
    if len(valid)!=min(len(candidates),CANDIDATE_LIMIT):
        complete=False
    ranked=sorted([comparison(data,embedded,profile) for profile in valid],key=lambda item:(-item.features['score'],item.issue_id))
    best=ranked[0] if ranked else None
    score=best.features['score'] if best else 0
    margin=score-(ranked[1].features['score'] if len(ranked)>1 else 0)
    exact=sum(item.features['exact'] and not item.features['blocked'] for item in ranked)
    blocked=bool(best and best.features['blocked'])
    prediction='match' if best and not blocked and (exact==1 or score>=.72) and margin>=.12 else 'new' if score<.35 and not any(item.features['exact'] for item in ranked) else 'ambiguous'
    # Empty or very weak extraction is never autonomous novelty.
    if not data['identifiers'] and not data['products']:
        prediction='ambiguous'
    bucket=f'{prediction}|exact={exact if exact<2 else 2}|sim={int(score*10)}|margin={min(3,int(max(0,margin)*10))}|ids={bool(identifiers)}|products={bool(data["products"])}|kind={data["kind"]}|complete={complete}'
    calibration=config.active_calibration
    metrics=calibration.metrics.get('buckets',{}).get(bucket,{}) if calibration and calibration.policy_version==MATCH_POLICY and calibration.metrics.get('embedding_model')==settings.NEWS_EMBEDDING_MODEL else {}
    confidence=metrics.get('confidence') if metrics.get('eligible') else None
    key=digest([proposal.pk,MATCH_POLICY,config.catalog_generation,calibration.pk if calibration else None,
                embedded.key if embedded else None,[(item.key) for item in ranked],complete])
    result,_=MatchAssessment.objects.get_or_create(key=key,defaults={'proposal':proposal,'catalog_generation':config.catalog_generation,
        'calibration':calibration,'prediction':prediction,'target_issue_id':best.issue_id if prediction=='match' else None,
        'bucket':bucket,'confidence':confidence,'evidence':{'policy':MATCH_POLICY,'identity_policy':POLICY_VERSION,
            'embedding_model':settings.NEWS_EMBEDDING_MODEL,'complete':complete,'margin':margin,
            'comparisons':[{'id':item.pk,'issue_id':item.issue_id,'identity_hash':item.identity_hash,'features':item.features} for item in ranked[:20]],
            'candidate_limit_hit':len(candidates)>CANDIDATE_LIMIT,'approximate_retrieval':True}})
    return result


def prepare_cache(proposals, *, limit=50, call=None):
    from .match_cache import embedding_provider
    provider=call or embedding_provider
    processed=0
    missing=Issue.objects.filter(current_version__isnull=False).filter(Q(match_profile__isnull=True)|
        ~Q(match_profile__source_version_id=F('current_version_id'))|Q(match_profile__embedding__isnull=True)|
        ~Q(match_profile__embedding__model=settings.NEWS_EMBEDDING_MODEL))
    for issue in missing.order_by('pk')[:limit]:
        profile=refresh_profile(issue.pk)
        if not profile.embedding_id or profile.embedding.model!=settings.NEWS_EMBEDDING_MODEL:
            embedding=get_embedding(profile.summary,prepare=True,call=provider)
            if embedding:
                IssueMatchProfile.objects.filter(pk=profile.pk,identity_hash=profile.identity_hash).update(embedding=embedding)
            processed+=1
            if processed>=limit:
                return processed
    for proposal in proposals:
        text=summary(extraction_data(proposal))
        if get_embedding(text) is None:
            get_embedding(text,prepare=True,call=provider)
            processed+=1
            if processed>=limit:
                break
    return processed


def process_pending(limit=50,prepare=False,call=None):
    config,_=MatchingConfiguration.objects.get_or_create(pk=1)
    work=MatchQueue.objects.exclude(status='resolved').filter(
        Q(status__in=['waiting','incomplete'])|~Q(catalog_generation=config.catalog_generation)|
        ~Q(calibration_id_snapshot=config.active_calibration_id or 0)|~Q(embedding_model=settings.NEWS_EMBEDDING_MODEL))
    work=list(work.select_related('proposal__decision').order_by(F('last_processed_at').asc(nulls_first=True),'pk')[:limit])
    proposals=[row.proposal for row in work if not hasattr(row.proposal,'decision')]
    if prepare:
        prepare_cache(proposals,limit=limit,call=call)
    results=[]
    for row in work:
        proposal=row.proposal
        if hasattr(proposal,'decision'):
            MatchQueue.objects.filter(pk=row.pk).update(status='resolved',last_processed_at=timezone.now())
            continue
        assessment=assess(proposal)
        from .match_review import apply_automatic
        decision=apply_automatic(assessment)
        MatchQueue.objects.filter(pk=row.pk).update(status='resolved' if decision and decision.outcome!='uncertain' else 'current' if assessment.evidence['complete'] else 'incomplete',
            catalog_generation=assessment.catalog_generation,calibration_id_snapshot=assessment.calibration_id or 0,
            embedding_model=settings.NEWS_EMBEDDING_MODEL,last_processed_at=timezone.now())
        results.append(assessment)
    return results


def wilson(success,total):
    if not total:
        return 0.0
    z=1.96
    p=success/total
    return (p+z*z/(2*total)-z*math.sqrt((p*(1-p)+z*z/(4*total))/total))/(1+z*z/total)
