"""Conservative browser gate. Uncertainty always means running both engines."""
import os
from pathlib import Path
import re
import subprocess

# Only isolated network subprocesses qualify. Shared Django code never does.
BROWSER_INDEPENDENT = frozenset({
    'news/analysis_provider.py',
    'news/embedding_provider.py',
    'news/feed_transport.py',
    'news/openai_probe.py',
    'news/slack_transport.py',
})


def select(changes):
    if not changes:
        return True, 'Empty or unavailable diff; run both browsers.'
    isolated=False
    for status,path in changes:
        if status!='M':
            return True, 'Added, deleted, renamed or unexpected file status; run both browsers.'
        if path=='VERSION':
            continue
        if path not in BROWSER_INDEPENDENT:
            return True, 'UI-related, shared or unrecognized file changed; run both browsers.'
        isolated=True
    if not isolated:
        return True, 'No qualifying isolated Python change; run both browsers.'
    return False, 'Only allowlisted isolated Python transport/provider modules and optional VERSION changed.'


def changed_files(base,head):
    if not all(re.fullmatch(r'[0-9a-fA-F]{40}',value or '') for value in (base,head)):
        raise ValueError('Missing or invalid commit SHA.')
    merge_base=subprocess.run(['git','merge-base',base,head],capture_output=True,check=True,timeout=30).stdout.decode().strip()
    if not re.fullmatch(r'[0-9a-fA-F]{40}',merge_base):
        raise ValueError('Invalid merge base.')
    raw=subprocess.run(['git','diff','--name-status','--no-renames','-z',merge_base,head,'--'],
                       capture_output=True,check=True,timeout=30).stdout.decode('utf-8')
    fields=raw.split('\0')
    if fields.pop()!='' or len(fields)%2:
        raise ValueError('Malformed diff.')
    return list(zip(fields[::2],fields[1::2]))


def decision(event,base='',head=''):
    if event!='pull_request':
        return True, 'Main push or manual/other event; run both browsers.'
    try:
        return select(changed_files(base,head))
    except Exception:
        return True, 'Unable to determine PR changes reliably; run both browsers.'


def main():
    run,reason=decision(os.environ.get('SELECTION_EVENT',''),os.environ.get('SELECTION_BASE',''),os.environ.get('SELECTION_HEAD',''))
    print(f'Browser tests: {"run" if run else "skip"}. {reason}')
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
        output.write(f'run_browsers={str(run).lower()}\n')
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
        summary.write(f'## Browser test selection\n\nDecision: **{"run Chromium and WebKit" if run else "skip Chromium and WebKit"}**\n\n{reason}\n\nFull Django tests, system/migration checks, Ruff and ESLint remain required.\n')


if __name__=='__main__':
    main()
