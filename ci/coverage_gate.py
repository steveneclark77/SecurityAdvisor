"""Enforce unrounded combined line/branch coverage for every measured module."""
import json
import os
from pathlib import Path
import sys

MINIMUM=90


def failures(report):
    if report.get('meta',{}).get('branch_coverage') is not True or not report.get('files'):
        raise ValueError('A nonempty branch-coverage report is required.')
    failed=[]
    for name,data in sorted(report['files'].items()):
        summary=data['summary']
        values=[summary[key] for key in ('covered_lines','num_statements','covered_branches','num_branches')]
        if any(type(value) is not int or value<0 for value in values):
            raise ValueError('Invalid coverage counts.')
        lines,total_lines,branches,total_branches=values
        if lines>total_lines or branches>total_branches:
            raise ValueError('Invalid coverage counts.')
        covered=lines+branches;total=total_lines+total_branches
        if total and covered*100<MINIMUM*total:
            failed.append((name,covered*100/total))
    return failed


def main():
    try:
        failed=failures(json.loads(Path(sys.argv[1] if len(sys.argv)>1 else 'coverage.json').read_text()))
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        print('Coverage gate failed: missing, malformed or non-branch coverage report.',file=sys.stderr)
        return 1
    lines=[f'Per-module coverage minimum: {MINIMUM}% (combined lines and branches; unrounded comparison).']
    lines.extend(f'{name}: {percent:.2f}% — below {MINIMUM}%' for name,percent in failed)
    lines.append(f'FAIL: {len(failed)} module(s) below minimum.' if failed else 'PASS: every measured module meets the minimum.')
    print('\n'.join(lines))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
            summary.write('\n## Per-module coverage gate\n\n```text\n'+'\n'.join(lines)+'\n```\n')
    return int(bool(failed))


if __name__=='__main__':
    sys.exit(main())
