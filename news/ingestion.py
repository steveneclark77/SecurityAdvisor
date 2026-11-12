"""Bounded, HTTPS-only RSS/Atom ingestion. Publisher text is untrusted data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from io import BytesIO
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

from defusedxml import ElementTree
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Issue, Scan, Source
from .feed_transport import validate_url

MAX_BYTES = 2 * 1024 * 1024


class IngestionQuotaExceeded(ValueError):
    pass


FEED_WORKER_COMMAND = [sys.executable, '-m', 'news.feed_transport']


def fetch_feed(url, *, timeout=30):
    """Kill and reap network work at the overall deadline, including DNS/headers."""
    result = subprocess.run(FEED_WORKER_COMMAND,
        input=json.dumps({'url': url, 'allowed_hosts': settings.NEWS_ALLOWED_HOSTS, 'app_version': settings.APP_VERSION}).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        cwd=Path(__file__).resolve().parent.parent, check=False)
    # subprocess.run kills and waits for the worker before raising on timeout.
    if result.returncode:
        raise ValueError('Feed transport failed; inspect endpoint and network policy.')
    if len(result.stdout) > MAX_BYTES:
        raise ValueError('Feed exceeds size limit.')
    return result.stdout


def text(element, name):
    child = next((child for child in element if child.tag.split('}')[-1] == name), None)
    return ''.join(child.itertext()).strip() if child is not None else ''


def published(value):
    if not value:
        return None
    try:
        date = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return date.replace(tzinfo=dt_timezone.utc) if date.tzinfo is None else date


def parse_feed(data):
    if len(data) > MAX_BYTES:
        raise ValueError('Feed exceeds size limit.')
    depth = nodes = entries_seen = 0
    iterator = ElementTree.iterparse(BytesIO(data), events=['start', 'end'])
    for event, node in iterator:
        if event == 'start':
            depth += 1
            nodes += 1
            if node.tag.split('}')[-1] in ['item', 'entry']:
                entries_seen += 1
            if depth > 64 or nodes > 10000 or entries_seen > 500:
                raise ValueError('Feed exceeds XML structure limits.')
        else:
            depth -= 1
    root = iterator.root
    kind = root.tag.split('}')[-1]
    if kind not in ['rss', 'feed', 'RDF']:
        raise ValueError('Response is not a supported RSS/Atom feed.')
    entries = [node for node in root.iter() if node.tag.split('}')[-1] in ['item', 'entry']]
    if len(entries) > 500:
        raise ValueError('Feed contains too many entries.')
    result = []
    for entry in entries:
        name = text(entry, 'title')
        url = text(entry, 'link')
        for link in entry:
            if link.tag.split('}')[-1] == 'link' and link.get('rel', 'alternate') == 'alternate' and link.get('href'):
                url = link.get('href')
                break
        if not name or not url:
            continue
        try:
            url = validate_url(url)
        except ValueError:
            continue
        if len(url) > 2000:
            continue
        # URL is stable even when a publisher rotates feed GUIDs.
        result.append({'identity': hashlib.sha256(url.encode()).hexdigest(), 'name': name[:500], 'url': url,
                       'description': (text(entry, 'description') or text(entry, 'summary') or text(entry, 'content'))[:20000],
                       'published_at': published(text(entry, 'pubDate') or text(entry, 'published') or text(entry, 'updated'))})
    return result


def scan_source(source_id, fetch=fetch_feed):
    source = Source.objects.get(pk=source_id)
    scan = Scan.objects.create(source=source, feed_url=source.feed_url)
    try:
        entries = parse_feed(fetch(source.feed_url))
        with transaction.atomic():
            # Serialize source writes on PostgreSQL; uniqueness is a second guard.
            Source.objects.select_for_update().get(pk=source_id)
            for entry in entries:
                identity = entry.pop('identity')
                from .versioning import create_version, CONTENT_FIELDS, reference_data
                issue, created = Issue.objects.get_or_create(source=source, identity=identity,
                    defaults={'first_scan': scan, 'last_seen_at': timezone.now()})
                if created:
                    if Issue.objects.filter(source=source).count() > settings.NEWS_MAX_ISSUES_PER_SOURCE:
                        raise IngestionQuotaExceeded('Publisher candidate quota reached.')
                    create_version(issue=issue, expected_version_id=None, content=entry, actor=None,
                        change_reason='First publisher feed discovery.', origin='publisher_ingestion',
                        references=[{'source_id': source.pk, 'source_url': entry['url'], 'source_published_at': entry['published_at'], 'notes': 'Publisher feed discovery.'}])
                    scan.created_count += 1
                else:
                    Issue.objects.filter(pk=issue.pk).update(last_seen_at=timezone.now())
                    previous_publisher = issue.versions.filter(origin__in=['publisher_ingestion', 'automated_proposal']).first()
                    publisher_fields = ['name', 'url', 'description', 'published_at']
                    if previous_publisher and any(getattr(previous_publisher, field) != entry[field] for field in publisher_fields):
                        if issue.versions.filter(origin__in=['publisher_ingestion', 'automated_proposal']).count() >= settings.NEWS_MAX_AUTO_VERSIONS_PER_ISSUE:
                            raise IngestionQuotaExceeded('Automated issue version quota reached.')
                        current = issue.current_version
                        content = {field: getattr(current, field) for field in CONTENT_FIELDS}
                        content.update(entry)
                        references = [ref for ref in reference_data(current) if ref['source_url'] != entry['url']]
                        references.append({'source_id': source.pk, 'source_url': entry['url'], 'source_published_at': entry['published_at'], 'notes': 'Changed publisher feed content; unverified proposal.'})
                        create_version(issue=issue, expected_version_id=current.pk, content=content, actor=None,
                            change_reason='Publisher feed content changed; consultant review required.', origin='automated_proposal', references=references)
        scan.status = 'success'
    except Exception as exc:
        scan.status = 'failed'
        scan.created_count = 0
        # Avoid persisting URLs, credentials, or remote response bodies in errors.
        scan.error = ('Storage quota reached; review NEWS_MAX_ISSUES_PER_SOURCE or NEWS_MAX_AUTO_VERSIONS_PER_ISSUE. Existing history was preserved.'
                      if isinstance(exc, IngestionQuotaExceeded) else f'{type(exc).__name__}: feed unavailable, blocked, oversized, or invalid. Check endpoint and network policy.')
    scan.finished_at = timezone.now()
    scan.save()
    return scan
