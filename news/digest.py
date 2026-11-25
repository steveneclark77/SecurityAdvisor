"""Daily local-time outbox; uncertain deliveries are never blindly retried."""
import json
import os
import subprocess
import sys
import uuid
from datetime import time
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from .models import DigestDelivery, InboxEvent
from .views import event_url

ZONE=ZoneInfo('America/Los_Angeles')


def transport(payload):
    result=subprocess.run([sys.executable,'-m','news.slack_transport'],input=json.dumps(payload).encode(),
        capture_output=True,timeout=60,cwd=Path(__file__).resolve().parent.parent,check=False)
    if result.returncode or len(result.stdout)>2048:
        return {'status':'unknown'}
    return json.loads(result.stdout)


def base_url():
    value=settings.NEWS_PUBLIC_BASE_URL.rstrip('/')
    parts=urlsplit(value)
    allowed_scheme=parts.scheme=='https' or (settings.DEBUG and parts.scheme=='http' and parts.hostname in ['localhost','127.0.0.1'])
    if not allowed_scheme or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('','/'):
        raise ValidationError('Configure NEWS_PUBLIC_BASE_URL as a credential-free HTTPS app origin.')
    return value


def payload_for(events,day):
    origin=base_url()
    blocks=[{'type':'header','text':{'type':'plain_text','text':f'SecurityAdvisor — {day.isoformat()}'}}]
    for kind,label in [('new','New issues'),('pending','Pending reviews'),('automatic_link','Automatic duplicate links')]:
        group=events.filter(kind=kind)
        count=group.count()
        if not count:
            continue
        blocks.append({'type':'section','text':{'type':'plain_text','text':f'{label}: {count}'}})
        for event in group.order_by('pk')[:10]:
            blocks.append({'type':'section','text':{'type':'plain_text','text':' '.join(event.title.split())[:200]},
                'accessory':{'type':'button','text':{'type':'plain_text','text':'Open in app'},'url':origin+event_url(event)}})
    blocks.append({'type':'actions','elements':[{'type':'button','text':{'type':'plain_text','text':'Review inbox'},'url':origin+'/news/'}]})
    return {'text':'SecurityAdvisor daily news digest','blocks':blocks,
            'client_msg_id':str(uuid.uuid5(uuid.NAMESPACE_URL,'securityadvisor/news-digest/'+str(day)))}


def send_digest(*,now=None,force=False,retry=False,call=transport):
    now=now or timezone.now()
    local=now.astimezone(ZONE)
    if not force and (not settings.NEWS_SLACK_DIGEST_ENABLED or local.time()<time(9)):
        return None
    if not os.environ.get('NEWS_SLACK_BOT_TOKEN'):
        raise ValidationError('Configure NEWS_SLACK_BOT_TOKEN before sending a digest.')
    base_url()
    with transaction.atomic():
        from .models import MatchingConfiguration
        MatchingConfiguration.objects.select_for_update().get(pk=1)
        blocked=DigestDelivery.objects.filter(status__in=['sending','unknown']).exists()
        if blocked:
            raise ValidationError('A Slack delivery is uncertain/in progress. Confirm its status before sending another digest.')
        delivery=DigestDelivery.objects.select_for_update().filter(day=local.date()).first()
        if delivery and (delivery.status in ['sent','skipped'] or not retry):
            return delivery
        if not delivery:
            last=DigestDelivery.objects.filter(status__in=['sent','skipped']).aggregate(last=Max('last_event_id'))['last'] or 0
            events=InboxEvent.objects.filter(pk__gt=last,kind__in=['new','pending','automatic_link'],created_at__lte=now).exclude(kind='pending',proposal__matching_work__status='resolved')
            high=InboxEvent.objects.filter(created_at__lte=now).aggregate(last=Max('pk'))['last'] or last
            if not events.exists():
                return DigestDelivery.objects.create(day=local.date(),status='skipped',first_event_id=last+1,last_event_id=high)
            delivery=DigestDelivery.objects.create(day=local.date(),first_event_id=last+1,last_event_id=high,
                payload=payload_for(events.filter(pk__lte=high),local.date()))
        delivery.status='sending';delivery.attempted_at=now;delivery.error=''
        delivery.save(update_fields=['status','attempted_at','error'])
    try:
        result=call(delivery.payload)
        status=result.get('status')
        if status not in ['sent','failed','unknown']:
            status='unknown'
    except Exception:
        status='unknown';result={}
    DigestDelivery.objects.filter(pk=delivery.pk,status='sending').update(status=status,finished_at=timezone.now(),
        slack_timestamp=str(result.get('timestamp',''))[:100] if status=='sent' else '',
        error='' if status=='sent' else 'Slack delivery unconfirmed; inspect channel before reconciliation.' if status=='unknown' else 'Slack workspace/channel/token validation failed. No message was confirmed.')
    delivery.refresh_from_db()
    return delivery
