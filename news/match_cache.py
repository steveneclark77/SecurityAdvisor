"""Content-addressed identity/embedding caches; no repeated LLM incident analysis."""
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import (Issue, IssueMatchProfile, IssueMatchKey, MatchingConfiguration,
                     EmbeddingCache, EmbeddingBucket, EmbeddingAttempt, AnalysisBudget)

POLICY_VERSION='identity-1'
DIMENSIONS=256


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def normalize(value):
    return ' '.join(re.findall(r'[a-z0-9]+',value.casefold()))[:200]


def identity_data(content, products=(), versions=()):
    identifiers=sorted({value for value in re.findall(r'\b(?:CVE-\d{4}-\d{4,}|GHSA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}|[A-Z][A-Z0-9]+-\d{4}-\d+)\b',content.get('identifiers','').upper()) if len(value)<=200})[:40]
    data={'name':content.get('name','').strip(),'description':content.get('description','')[:10000],
          'kind':content.get('kind','unclassified'),'identifiers':identifiers,
          'products':sorted(set(normalize(item) for item in products if normalize(item)))[:20],
          'versions':sorted(set(normalize(item) for item in versions if normalize(item)))[:20]}
    return data


def summary(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True)


@transaction.atomic
def refresh_profile(issue_id, products=None, versions=None):
    issue=Issue.objects.select_for_update(of=('self',)).select_related('current_version').get(pk=issue_id)
    if not issue.current_version_id:
        return None
    current=IssueMatchProfile.objects.filter(issue=issue).first()
    content={key:getattr(issue.current_version,key) for key in ['name','description','kind','identifiers']}
    # Severity/remediation-only edits retain the semantic identity and its cache.
    old=current.fingerprint if current else {}
    same_base=all(old.get(key)==identity_data(content).get(key) for key in ['name','description','kind','identifiers'])
    data=identity_data(content,products if products is not None else old.get('products',[]) if same_base else [],
                       versions if versions is not None else old.get('versions',[]) if same_base else [])
    fingerprint=digest([POLICY_VERSION,data])
    if current and current.identity_hash==fingerprint:
        if current.source_version_id!=issue.current_version_id:
            IssueMatchProfile.objects.filter(pk=current.pk).update(source_version_id=issue.current_version_id)
        return current
    profile,_=IssueMatchProfile.objects.update_or_create(issue=issue,defaults={
        'source_version_id':issue.current_version_id,'identity_hash':fingerprint,'summary':summary(data),'fingerprint':data,'embedding':None})
    profile.keys.all().delete()
    tokens=sorted({word[:200] for word in re.findall(r'[a-z0-9]{4,}',data['name'].lower())})[:20]
    keys=[('identifier',item) for item in data['identifiers']]+[('product',item) for item in data['products']]+[('token',item) for item in tokens]
    IssueMatchKey.objects.bulk_create([IssueMatchKey(profile=profile,kind=kind,value=value) for kind,value in keys])
    MatchingConfiguration.objects.get_or_create(pk=1)
    MatchingConfiguration.objects.filter(pk=1).update(catalog_generation=F('catalog_generation')+1)
    return profile


def extraction_data(proposal):
    return identity_data(proposal.content,proposal.matching.get('affected_products',[]),proposal.matching.get('affected_versions',[]))


def embedding_key(text):
    return digest([settings.NEWS_EMBEDDING_MODEL,DIMENSIONS,digest(text)])


@lru_cache(maxsize=1)
def projections():
    rng=random.Random(718231)
    return [[rng.gauss(0,1) for _ in range(DIMENSIONS)] for _ in range(96)]


def bucket_keys(vector):
    bits=[sum(a*b for a,b in zip(vector,plane,strict=True))>=0 for plane in projections()]
    return [f'{band}:'+''.join('1' if bit else '0' for bit in bits[band*12:(band+1)*12]) for band in range(8)]


def embedding_provider(text):
    payload={'model':settings.NEWS_EMBEDDING_MODEL,'input':text,'dimensions':DIMENSIONS}
    result=subprocess.run([sys.executable,'-m','news.embedding_provider'],input=json.dumps(payload).encode(),
        capture_output=True,timeout=60,cwd=Path(__file__).resolve().parent.parent,check=False)
    if result.returncode or len(result.stdout)>1024*1024:
        raise ValidationError('Embedding request failed.')
    return json.loads(result.stdout)


def get_embedding(text, *, prepare=False, call=embedding_provider):
    key=embedding_key(text)
    cached=EmbeddingCache.objects.filter(key=key).first()
    if cached or not prepare:
        return cached
    if len(text.encode())>40000:
        raise ValidationError('Embedding input is too large.')
    import os
    if not os.environ.get('NEWS_ANALYSIS_API_KEY'):
        raise ValidationError('Configure NEWS_ANALYSIS_API_KEY before preparing embeddings.')
    with transaction.atomic():
        # One shared configuration lock prevents duplicate concurrent provider calls.
        configuration=MatchingConfiguration.objects.select_for_update().get(pk=1)
        cached=EmbeddingCache.objects.filter(key=key).first()
        if cached:
            return cached
        from datetime import timedelta
        active=EmbeddingAttempt.objects.filter(key=key,status='running')
        active.filter(started_at__lt=timezone.now()-timedelta(minutes=5)).update(status='failed',finished_at=timezone.now(),error='Interrupted embedding attempt; reservation retained.')
        if active.exists():
            return None
        if EmbeddingAttempt.objects.filter(key=key).count()>=settings.NEWS_ANALYSIS_MAX_ATTEMPTS:
            return None
        cap=settings.NEWS_EMBEDDING_PER_RUN_CENTS
        from decimal import Decimal, ROUND_CEILING, InvalidOperation
        try:
            price=Decimal(settings.NEWS_EMBEDDING_INPUT_PRICE)
        except InvalidOperation:
            raise ValidationError('Configure a valid embedding price.') from None
        if not price.is_finite() or price<=0:
            raise ValidationError('Configure a positive finite embedding price.')
        estimate=(Decimal(len(text.encode())+100)*price/Decimal(10000)).to_integral_value(rounding=ROUND_CEILING)
        if not price.is_finite() or price<=0 or estimate>cap or cap<=0 or cap>settings.NEWS_ANALYSIS_DAILY_CENTS:
            raise ValidationError('Invalid embedding reservation limit.')
        budget,_=AnalysisBudget.objects.get_or_create(day=timezone.now().date())
        if not AnalysisBudget.objects.filter(pk=budget.pk,reserved_cents__lte=settings.NEWS_ANALYSIS_DAILY_CENTS-cap).update(reserved_cents=F('reserved_cents')+cap):
            raise ValidationError('Daily shared analysis/embedding budget exhausted.')
        attempt=EmbeddingAttempt.objects.create(key=key,model=settings.NEWS_EMBEDDING_MODEL,content_hash=digest(text),reserved_cents=cap)
        del configuration
    try:
        result=call(text)
        vector=result['vector']
        if not isinstance(vector,list) or len(vector)!=DIMENSIONS or any(type(v) not in (int,float) or not math.isfinite(v) for v in vector):
            raise ValidationError('Invalid embedding vector.')
        norm=math.sqrt(sum(value*value for value in vector))
        if not math.isfinite(norm) or norm<=0:
            raise ValidationError('Invalid embedding norm.')
        vector=[value/norm for value in vector]
        tokens=result.get('tokens',0)
        if type(tokens) is not int or not 0<=tokens<=50000:
            raise ValidationError('Invalid embedding usage.')
        with transaction.atomic():
            locked=EmbeddingAttempt.objects.select_for_update().get(pk=attempt.pk)
            if locked.status!='running':
                return None
            cached=EmbeddingCache.objects.create(key=key,model=settings.NEWS_EMBEDDING_MODEL,content_hash=digest(text),vector=vector)
            EmbeddingBucket.objects.bulk_create([EmbeddingBucket(embedding=cached,key=value) for value in bucket_keys(vector)])
            EmbeddingAttempt.objects.filter(pk=attempt.pk).update(status='succeeded',finished_at=timezone.now(),tokens=tokens)
        return cached
    except Exception:
        EmbeddingAttempt.objects.filter(pk=attempt.pk,status='running').update(status='failed',finished_at=timezone.now(),error='Embedding request failed or returned invalid data; retry is bounded. No remote body retained.')
        return None
