"""Isolated, bounded OpenAI request. No database, customer data, tools or redirects."""
import json
import os
import sys
import urllib.request

MAX_RESPONSE = 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Provider redirects are not allowed.')


def request_analysis(payload):
    key = os.environ.get('NEWS_ANALYSIS_API_KEY', '')
    if not key:
        raise ValueError('Analysis credentials are not configured.')
    request = urllib.request.Request('https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type':'application/json', 'Authorization':'Bearer '+key})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Provider response exceeded its limit.')
    result = json.loads(raw)
    choice = result['choices'][0]
    if choice.get('finish_reason') != 'stop' or choice['message'].get('refusal'):
        raise ValueError('Provider did not return complete analysis.')
    return {'output':json.loads(choice['message']['content']), 'usage':result['usage']}


if __name__ == '__main__':
    try:
        result = request_analysis(json.loads(sys.stdin.buffer.read(512 * 1024)))
        sys.stdout.write(json.dumps(result))
    except Exception:
        # Do not expose API keys, response bodies or publisher content in logs.
        sys.stderr.write('Analysis provider request failed.\n')
        sys.exit(1)
