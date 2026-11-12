"""Network-only feed worker; no application models or database connections."""
import http.client
import ipaddress
import json
import socket
import sys
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
from django.conf import settings

MAX_BYTES = 2 * 1024 * 1024


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError('Feed must resolve exclusively to public addresses.')
    return addresses[0][4][0]


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Keep hostname TLS verification while dialing the checked public IP."""
    def connect(self):
        target = self._tunnel_host or self.host
        if target not in settings.NEWS_ALLOWED_HOSTS:
            raise ValueError('Feed host is not allowed.')
        self._pinned_ip = public_address(target)
        through_proxy = bool(self._tunnel_host)
        original = self._create_connection
        def dial(address, *args, **kwargs):
            return original(address if through_proxy else (self._pinned_ip, address[1]), *args, **kwargs)
        self._create_connection = dial
        try:
            super().connect()
        finally:
            self._create_connection = original

    def _tunnel(self):
        # The CONNECT target is the validated IP, while TLS still verifies and
        # sends SNI for the original publisher hostname after this returns.
        hostname = self._tunnel_host
        self._tunnel_host = self._pinned_ip
        try:
            super()._tunnel()
        finally:
            self._tunnel_host = hostname


class PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(PinnedHTTPSConnection, req, context=self._context)


def validate_url(url, *, feed=False):
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Only credential-free HTTPS URLs on port 443 are supported.')
    if feed:
        if parts.hostname not in settings.NEWS_ALLOWED_HOSTS:
            raise ValueError('Feed host is not in NEWS_ALLOWED_HOSTS.')
        public_address(parts.hostname)
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
    with build_opener(SafeRedirect(), PinnedHTTPSHandler()).open(request, timeout=10) as response:
        chunks = []
        size = 0
        while True:
            chunk = response.read1(65536)
            size += len(chunk)
            if size > MAX_BYTES or time.monotonic() - started > 30:
                raise ValueError('Feed exceeds size or duration limit.')
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)



if __name__ == '__main__':
    payload = json.load(sys.stdin)
    settings.configure(NEWS_ALLOWED_HOSTS=payload['allowed_hosts'], APP_VERSION=payload['app_version'])
    try:
        data = fetch_feed(payload['url'])
    except Exception as exc:
        # Never emit remote bodies, URLs, or proxy credentials to the parent.
        sys.stderr.write(type(exc).__name__)
        raise SystemExit(1)
    sys.stdout.buffer.write(data)
