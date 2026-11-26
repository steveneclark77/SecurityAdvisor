"""Local diagnostics and an explicit, bounded OpenAI test; no database access."""
import json
import os
from pathlib import Path
import subprocess
import sys
from django.conf import settings
from django.core.management.base import CommandError

STATUSES={
    'ok':'passed',
    'authentication_failed':'authentication failed; check NEWS_ANALYSIS_API_KEY',
    'access_denied':'access denied; check project/model permissions',
    'model_unavailable':'model unavailable; check the configured model',
    'quota_or_rate_limit':'quota or rate limit reached; check billing and limits',
    'provider_error':'provider error; check service availability',
    'invalid_response':'unexpected provider response',
    'request_failed':'request failed; check network, TLS and model configuration',
}


def configuration_status():
    key=bool(os.environ.get('NEWS_ANALYSIS_API_KEY','').strip())
    models=bool(settings.NEWS_ANALYSIS_MODEL.strip() and settings.NEWS_EMBEDDING_MODEL.strip())
    enabled='enabled' if settings.NEWS_ANALYSIS_ENABLED else 'disabled'
    return f'OpenAI configuration: automatic analysis {enabled}; API key {"configured" if key else "missing"}; models {"configured" if models else "missing"}. Local check only; no API call or credential validation.'


def test_connection():
    if not os.environ.get('NEWS_ANALYSIS_API_KEY','').strip():
        raise CommandError('Configure NEWS_ANALYSIS_API_KEY in the analysis worker.')
    if not settings.NEWS_ANALYSIS_MODEL.strip() or not settings.NEWS_EMBEDDING_MODEL.strip():
        raise CommandError('Configure both NEWS_ANALYSIS_MODEL and NEWS_EMBEDDING_MODEL.')
    try:
        result=subprocess.run([sys.executable,'-m','news.openai_probe'],
            input=json.dumps({'analysis':settings.NEWS_ANALYSIS_MODEL,'embeddings':settings.NEWS_EMBEDDING_MODEL}).encode(),
            capture_output=True,timeout=70,check=False,cwd=Path(__file__).resolve().parent.parent)
        if result.returncode or len(result.stdout)>4096:
            raise ValueError
        outcomes=json.loads(result.stdout)
        if len(outcomes)!=2 or [v['kind'] for v in outcomes]!=['analysis','embeddings']:
            raise ValueError
        messages=[f"OpenAI {v['kind']}: {STATUSES[v['status']]}" for v in outcomes]
    except Exception:
        raise CommandError('OpenAI test failed or timed out. Remote error details are not logged; no automatic retry.') from None
    if any(v['status']!='ok' for v in outcomes):
        raise CommandError('; '.join(messages))
    return '; '.join(messages)+'. Synthetic requests only; no application records changed.'
