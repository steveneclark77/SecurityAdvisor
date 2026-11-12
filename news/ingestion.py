"""Bounded, HTTPS-only RSS/Atom ingestion. Publisher text is untrusted data."""
import hashlib
import ipaddress
import socket
import time
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from defusedxml import ElementTree
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Issue, Scan, Source

MAX_BYTES = 2 * 1024 * 1024


def validate_url(url, *, feed=False):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Only credential-free HTTPS URLs on port 443 are supported.')
    if feed:
        if parts.hostname not in settings.NEWS_ALLOWED_HOSTS:
            raise ValueError('Feed host is not in NEWS_ALLOWED_HOSTS.')
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ValueError('Feed must resolve exclusively to public addresses.')
    return urlunsplit(('https', parts.netloc.lower(), parts.path or '/', parts.query, ''))


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl, feed=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_feed(url):
    validate_url(url, feed=True)
    request = Request(url, headers={'User-Agent': f'SecurityAdvisor/{settings.APP_VERSION} (+RSS reader)', 'Accept': 'application/rss+xml, application/atom+xml, application/xml', 'Accept-Encoding': 'identity'})
    # Keep inherited proxy and CA settings; redirects are checked before sending.
    started = time.monotonic()
    with build_opener(SafeRedirect()).open(request, timeout=10) as response:
        chunks = []
        size = 0
        while True:
            chunk = response.read(65536)
            size += len(chunk)
            if size > MAX_BYTES or time.monotonic() - started > 30:
                raise ValueError('Feed exceeds size or duration limit.')
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)


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
    root = ElementTree.fromstring(data)
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
                issue, created = Issue.objects.get_or_create(source=source, identity=identity,
                    defaults={**entry, 'first_scan': scan, 'last_seen_at': timezone.now()})
                if created:
                    scan.created_count += 1
                else:
                    Issue.objects.filter(pk=issue.pk).update(last_seen_at=timezone.now())
        scan.status = 'success'
    except Exception as exc:
        scan.status = 'failed'
        scan.created_count = 0
        # Avoid persisting URLs, credentials, or remote response bodies in errors.
        scan.error = f'{type(exc).__name__}: feed unavailable, blocked, oversized, or invalid. Check endpoint and network policy.'
    scan.finished_at = timezone.now()
    scan.save()
    return scan
