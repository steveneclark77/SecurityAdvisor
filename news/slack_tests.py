"""Explicit connection tests; never consume or advance the daily digest window."""
import os
import re
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from .digest import base_url,transport
from .models import SlackTestRequest
from .slack_transport import diagnostic


def configuration_status():
    token=bool(os.environ.get('NEWS_SLACK_BOT_TOKEN','').strip())
    try:
        base_url();origin='valid'
    except (ValidationError,ValueError):
        origin='missing or invalid'
    enabled='enabled' if settings.NEWS_SLACK_DIGEST_ENABLED else 'disabled'
    return f'Slack configuration: daily digest {enabled}; bot token {"configured" if token else "missing"}; app origin {origin}. Local check only; no message sent.'


def deliver_test(pk,call=None):
    if not SlackTestRequest.objects.filter(pk=pk,status='pending').update(status='sending',started_at=timezone.now()):
        return SlackTestRequest.objects.get(pk=pk)
    try:
        if not os.environ.get('NEWS_SLACK_BOT_TOKEN','').strip():
            result={'status':'failed','error_code':'missing_token'}
        else:
            try:
                origin=base_url()
            except (ValidationError,ValueError):
                result={'status':'failed','error_code':'invalid_origin'}
                SlackTestRequest.objects.filter(pk=pk,status='sending').update(status='failed',finished_at=timezone.now(),message=diagnostic(result))
                return SlackTestRequest.objects.get(pk=pk)
            stamp=timezone.now().isoformat()
            payload={'text':'SecurityAdvisor Slack connection test','client_msg_id':str(SlackTestRequest.objects.only('request_uuid').get(pk=pk).request_uuid),
                'blocks':[{'type':'section','text':{'type':'plain_text','text':f'[TEST] SecurityAdvisor v{settings.APP_VERSION} Slack connection test\nRequested test notification #{pk} — {stamp}'}},
                    {'type':'actions','elements':[{'type':'button','text':{'type':'plain_text','text':'Open SecurityAdvisor'},'url':origin+'/news/'}]}]}
            result=(call or transport)(payload)
        status=result.get('status')
        if status not in ['sent','failed','unknown']:
            result={'status':'unknown','error_code':'delivery_unconfirmed'};status='unknown'
        timestamp=str(result.get('timestamp',''))
        if status=='sent' and (len(timestamp)>100 or not re.fullmatch(r'[0-9]+\.[0-9]+',timestamp)):
            result={'status':'unknown','error_code':'delivery_unconfirmed'};status='unknown'
        message=diagnostic(result)
    except Exception:
        status='unknown';result={};message=diagnostic({'status':'unknown'})
    SlackTestRequest.objects.filter(pk=pk,status='sending').update(status=status,finished_at=timezone.now(),message=message[:300],
        slack_timestamp=str(result.get('timestamp',''))[:100] if status=='sent' else '')
    return SlackTestRequest.objects.get(pk=pk)


def process_test_requests(limit=5):
    SlackTestRequest.objects.filter(status='sending',started_at__lt=timezone.now()-timedelta(minutes=5)).update(
        status='unknown',finished_at=timezone.now(),message=diagnostic({'status':'unknown'}))
    ids=list(SlackTestRequest.objects.filter(status='pending').order_by('pk').values_list('pk',flat=True)[:limit])
    return [deliver_test(pk) for pk in ids]
