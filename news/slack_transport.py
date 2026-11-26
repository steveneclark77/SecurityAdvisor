"""Network-only Slack delivery shared by digests and explicit connection tests."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from .analysis_provider import NoRedirect

MESSAGES={
    'invalid_origin':'Configure NEWS_PUBLIC_BASE_URL as a valid app origin before testing.',
    'missing_token':'Configure NEWS_SLACK_BOT_TOKEN in the notification worker.',
    'invalid_auth':'Slack rejected the bot token. Check or replace NEWS_SLACK_BOT_TOKEN.',
    'not_authed':'Slack requires a bot token. Check NEWS_SLACK_BOT_TOKEN.',
    'token_revoked':'The Slack bot token was revoked. Reinstall the app and configure its new token.',
    'token_expired':'The Slack bot token expired. Configure a current bot token.',
    'account_inactive':'The Slack bot account is inactive. Check the app installation.',
    'missing_scope':'The bot lacks a required scope: channels:read for public channels, groups:read for private channels, and chat:write to post. Reinstall after changes.',
    'workspace_mismatch':'The bot belongs to a different workspace. Use the securityadvisor-talk.slack.com workspace installation.',
    'channel_not_found':'The security-advisor-notifications channel was not found. Check its name, bot membership and read scopes.',
    'not_in_channel':'Invite the bot to security-advisor-notifications before posting.',
    'is_archived':'The notification channel is archived. Restore it before posting.',
    'rate_limited':'Slack rate-limited the request. Wait before explicitly testing again.',
    'restricted_action':'Slack workspace policy prevents this action. Check app approval and bot permissions.',
    'not_allowed_token_type':'Use the Bot User OAuth Token, not an app-level or configuration token.',
    'org_login_required':'Slack requires the app installation to be reauthorized.',
    'connection_failed':'Unable to validate Slack connectivity. Check network access, TLS and Slack availability.',
    'slack_error':'Slack rejected the operation. Check the app installation and permissions.',
    'delivery_unconfirmed':'Delivery is unconfirmed. Check the channel before sending another test; the message may already be present.',
}


class SlackAPIError(ValueError):
    def __init__(self,code):
        self.code=code if isinstance(code,str) and code in MESSAGES else 'slack_error'
        super().__init__(self.code)


def diagnostic(result):
    if result.get('status')=='sent':
        return 'Test message sent to securityadvisor / security-advisor-notifications.'
    fallback='delivery_unconfirmed' if result.get('status')=='unknown' else 'slack_error'
    return MESSAGES.get(result.get('error_code'),MESSAGES[fallback])


def api(method,payload):
    if method not in ['auth.test','conversations.list','chat.postMessage']:
        raise SlackAPIError('slack_error')
    token=os.environ.get('NEWS_SLACK_BOT_TOKEN','').strip()
    if not token:
        raise SlackAPIError('missing_token')
    request=urllib.request.Request('https://slack.com/api/'+method,data=json.dumps(payload).encode(),headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json; charset=utf-8'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
            raw=response.read(1024*1024+1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401,403):
            raise SlackAPIError('invalid_auth' if exc.code==401 else 'restricted_action') from None
        if exc.code==429:
            raise SlackAPIError('rate_limited') from None
        # A server/network error after POST might have followed accepted delivery.
        raise OSError('Slack HTTP request failed.') from None
    if len(raw)>1024*1024:
        raise ValueError('Slack response limit.')
    result=json.loads(raw)
    if not result.get('ok'):
        code=result.get('error')
        raise SlackAPIError('rate_limited' if code=='ratelimited' else code)
    return result


def find_channel():
    # Public channels do not require private-channel read access. Only try private
    # discovery if the configured channel was not found in the public list.
    for visibility in ['public_channel','private_channel']:
        cursor=''
        for _ in range(10):
            result=api('conversations.list',{'exclude_archived':True,'limit':200,'cursor':cursor,'types':visibility})
            channel=next((item for item in result.get('channels',[]) if item.get('name')=='security-advisor-notifications'),None)
            if channel:
                if channel.get('is_archived'):
                    raise SlackAPIError('is_archived')
                if channel.get('is_member') is False:
                    raise SlackAPIError('not_in_channel')
                return channel
            cursor=result.get('response_metadata',{}).get('next_cursor','')
            if not cursor:
                break
    raise SlackAPIError('channel_not_found')


def send(payload):
    try:
        auth=api('auth.test',{})
        if urllib.parse.urlsplit(auth.get('url','')).hostname!='securityadvisor-talk.slack.com':
            raise SlackAPIError('workspace_mismatch')
        channel=find_channel()
    except SlackAPIError as exc:
        return {'status':'failed','error_code':exc.code}
    except Exception:
        return {'status':'failed','error_code':'connection_failed'}
    try:
        result=api('chat.postMessage',{**payload,'channel':channel['id'],'unfurl_links':False,'unfurl_media':False,'parse':'none'})
        timestamp=str(result.get('ts',''))
        if len(timestamp)>100 or not re.fullmatch(r'[0-9]+\.[0-9]+',timestamp):
            return {'status':'unknown','error_code':'delivery_unconfirmed'}
        return {'status':'sent','timestamp':timestamp}
    except SlackAPIError as exc:
        if exc.code in {'missing_token','invalid_auth','not_authed','token_revoked','token_expired',
            'account_inactive','missing_scope','channel_not_found','not_in_channel','is_archived',
            'rate_limited','restricted_action','not_allowed_token_type','org_login_required'}:
            return {'status':'failed','error_code':exc.code}
        return {'status':'unknown','error_code':'delivery_unconfirmed'}
    except Exception:
        return {'status':'unknown','error_code':'delivery_unconfirmed'}


if __name__=='__main__':
    try:
        sys.stdout.write(json.dumps(send(json.loads(sys.stdin.buffer.read(256*1024)))))
    except Exception:
        sys.stdout.write(json.dumps({'status':'unknown','error_code':'delivery_unconfirmed'}))
