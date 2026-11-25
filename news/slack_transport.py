"""Network-only Slack digest delivery. Fixed host; no redirects or remote error bodies."""
import json
import os
import sys
import urllib.parse
import urllib.request
from .analysis_provider import NoRedirect


def api(method,payload):
    if method not in ['auth.test','conversations.list','chat.postMessage']:
        raise ValueError('Unsupported Slack operation.')
    token=os.environ.get('NEWS_SLACK_BOT_TOKEN','')
    if not token:
        raise ValueError('Slack token missing.')
    request=urllib.request.Request('https://slack.com/api/'+method,data=json.dumps(payload).encode(),headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json; charset=utf-8'})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
        raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:
        raise ValueError('Slack response limit.')
    result=json.loads(raw)
    if not result.get('ok'):
        raise ValueError('Slack operation rejected.')
    return result


def send(payload):
    try:
        auth=api('auth.test',{})
        if urllib.parse.urlsplit(auth.get('url','')).hostname!='securityadvisor.slack.com':
            raise ValueError('Slack workspace does not match.')
        cursor='';channel=None
        for _ in range(10):
            result=api('conversations.list',{'exclude_archived':True,'limit':200,'cursor':cursor,'types':'public_channel,private_channel'})
            channel=next((item for item in result.get('channels',[]) if item.get('name')=='security-advisor-notifications' and not item.get('is_archived')),None)
            if channel:
                break
            cursor=result.get('response_metadata',{}).get('next_cursor','')
            if not cursor:
                break
        if not channel:
            raise ValueError('Configured channel not available to bot.')
    except Exception:
        return {'status':'failed'}
    try:
        result=api('chat.postMessage',{**payload,'channel':channel['id'],'unfurl_links':False,'unfurl_media':False,'parse':'none'})
        return {'status':'sent','timestamp':str(result.get('ts',''))[:100]}
    except Exception:
        # Once POST begins, a timeout/error may mean Slack accepted the message.
        return {'status':'unknown'}


if __name__=='__main__':
    try:
        sys.stdout.write(json.dumps(send(json.loads(sys.stdin.buffer.read(256*1024)))))
    except Exception:
        sys.stdout.write(json.dumps({'status':'unknown'}))
