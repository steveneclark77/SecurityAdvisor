from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from library.models import Baseline
from .ingestion import parse_feed, scan_source, validate_url, SafeRedirect
from .models import Issue, Review, Scan, Source

RSS = b'''<rss><channel><item><title>Synthetic vulnerability</title><link>https://example.test/advisory</link><description>Unverified publisher excerpt</description><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'''


class IngestionTests(TestCase):
    def setUp(self):
        Source.objects.all().update(enabled=False)
        self.source = Source.objects.create(name='Synthetic feed', url='https://example.test/', feed_url='https://example.test/rss', enabled=True)

    def test_seeded_publishers(self):
        self.assertEqual(Source.objects.exclude(pk=self.source.pk).count(), 3)

    def test_idempotent_and_preserves_reviewed_content(self):
        scan = scan_source(self.source.pk, lambda url: RSS)
        self.assertEqual((scan.status, scan.created_count), ('success', 1))
        issue = Issue.objects.get()
        self.assertEqual(issue.severity, 'unknown')
        self.assertEqual(issue.remediation, '')
        self.assertIsNotNone(issue.published_at)
        issue.remediation = 'Reviewed synthetic action'
        issue.save()
        second = scan_source(self.source.pk, lambda url: RSS.replace(b'Unverified publisher excerpt', b'Updated text'))
        self.assertEqual(second.created_count, 0)
        issue.refresh_from_db()
        self.assertEqual(issue.remediation, 'Reviewed synthetic action')
        self.assertEqual(issue.description, 'Unverified publisher excerpt')
        self.assertEqual(issue.first_scan, scan)

    def test_atom_and_unsafe_article_links(self):
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Practice</title><link href="https://example.test/practice"/><summary>Summary</summary><updated>2026-11-11T10:00:00Z</updated></entry></feed>'
        self.assertEqual(parse_feed(atom)[0]['name'], 'Practice')
        self.assertEqual(parse_feed(RSS.replace(b'https://example.test/advisory', b'javascript:alert(1)')), [])

    def test_xml_entities_and_partial_malformed_feed_fail_closed(self):
        for data in [b'<html>Access denied</html>', b'<rss>', b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss>&x;</rss>']:
            scan = scan_source(self.source.pk, lambda url: data)
            self.assertEqual(scan.status, 'failed')
            self.assertFalse(Issue.objects.exists())

    def test_network_failure_is_recorded_without_secret(self):
        def fail(url):
            raise RuntimeError('secret-token')
        scan = scan_source(self.source.pk, fail)
        self.assertEqual(scan.status, 'failed')
        self.assertNotIn('secret-token', scan.error)
        self.assertIsNotNone(scan.finished_at)

    @override_settings(NEWS_ALLOWED_HOSTS=['example.test'])
    def test_feed_network_boundaries_and_redirects(self):
        for url in ['http://example.test/feed', 'https://user:password@example.test/', 'https://example.test:444/', 'https://internal.test/rss']:
            with self.assertRaises(ValueError):
                validate_url(url, feed=True)
        with patch('news.ingestion.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                validate_url('https://example.test/rss', feed=True)
        with self.assertRaises(ValueError):
            SafeRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1/')

    def test_baseline_gate_and_disabled_sources(self):
        with patch('news.management.commands.scan_news.scan_source') as scan:
            with self.assertRaises(CommandError):
                call_command('scan_news')
            scan.assert_not_called()
        user = get_user_model().objects.create_user('synthetic')
        Baseline.objects.create(version='synthetic', created_by=user, snapshot={}, coverage_gaps='Synthetic only', approved_by=user, approved_at=timezone.now())
        with patch('news.management.commands.scan_news.scan_source') as scan:
            scan.return_value = Scan(status='success', created_count=0)
            call_command('scan_news', stdout=StringIO())
            scan.assert_called_once_with(self.source.pk)

    def test_review_requires_guidance_and_no_self_duplicate(self):
        scan_source(self.source.pk, lambda url: RSS)
        issue = Issue.objects.get()
        review = Review(issue=issue, decision='add', rationale='Synthetic test')
        with self.assertRaises(ValidationError):
            review.clean()
        review.proposed_guidance = 'Review identity configuration'
        review.duplicate_of = issue
        with self.assertRaises(ValidationError):
            review.clean()

    def test_staff_without_permission_cannot_access_sources(self):
        user = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/news/source/').status_code, 403)

    def test_feed_size_limit(self):
        from contextlib import contextmanager
        from .ingestion import fetch_feed, MAX_BYTES
        class Oversized:
            def read1(self, size):
                return b'x' * size
        @contextmanager
        def response(*args, **kwargs):
            yield Oversized()
        with patch('news.ingestion.validate_url'), patch('news.ingestion.build_opener') as opener:
            opener.return_value.open.side_effect = response
            with self.assertRaises(ValueError):
                fetch_feed('https://example.test/rss')
        self.assertGreater(MAX_BYTES, 0)

    def test_admin_csrf_and_preserved_review_snapshot(self):
        from django.test import Client
        scan_source(self.source.pk, lambda url: RSS)
        issue = Issue.objects.get()
        user = get_user_model().objects.create_superuser('reviewer', password='synthetic-password')
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        path = '/admin/news/review/add/'
        client.get(path)
        token = client.cookies['csrftoken'].value
        data = {'issue': issue.pk, 'decision': 'ignore', 'rationale': 'Synthetic unrelated report', '_save': 'Save'}
        self.assertEqual(client.post(path, data).status_code, 403)
        for origin in ['null', 'https://foreign.test']:
            self.assertEqual(client.post(path, {**data, 'csrfmiddlewaretoken': token}, HTTP_ORIGIN=origin).status_code, 403)
        self.assertEqual(client.post(path, {**data, 'csrfmiddlewaretoken': token}, HTTP_ORIGIN='http://testserver').status_code, 302)
        review = Review.objects.get()
        self.assertEqual(review.actor, user)
        self.assertEqual(review.issue_snapshot['severity'], 'unknown')
        issue.severity = 'high'
        issue.save()
        review.refresh_from_db()
        self.assertEqual(review.issue_snapshot['severity'], 'unknown')
        self.assertEqual(client.post(f'/admin/news/review/{review.pk}/change/', {**data, 'csrfmiddlewaretoken': token}).status_code, 403)
        self.assertEqual(client.post(f'/admin/news/issue/{issue.pk}/delete/', {'csrfmiddlewaretoken': token}).status_code, 403)
