"""Stable website identifiers, separate from mutable feed endpoints."""
from urllib.parse import quote, urlsplit, urlunsplit
from django.core.exceptions import ValidationError


def canonical_source_url(value):
    try:
        parts = urlsplit(value.strip())
        if parts.scheme.lower() != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443) or parts.query:
            raise ValueError
        hostname = parts.hostname.encode('idna').decode('ascii').lower()
        hostname = f'[{hostname}]' if ':' in hostname else hostname
        path = quote(parts.path.rstrip('/') or '/', safe="/:@!$&'()*+,;=-._~%")
        result = urlunsplit(('https', hostname, path, '', ''))
        if len(result) > 1000:
            raise ValueError
        return result
    except (ValueError, UnicodeError, AttributeError) as exc:
        raise ValidationError('Use a credential-free HTTPS website URL without a query string, at most 1000 characters.') from exc
