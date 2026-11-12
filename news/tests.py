from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from library.models import Baseline
from .ingestion import parse_feed, scan_source, validate_url, SafeRedirect
from .models import Issue, IssueVersion, IssueVersionReference, Review, Scan, Source
from .versioning import create_version, CONTENT_FIELDS

RSS = b'''<rss><channel><item><title>Synthetic vulnerability</title><link>https://example.test/advisory</link><description>Unverified publisher excerpt</description><pubDate>Wed, 11 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'''


class IngestionTests(TestCase):
    def setUp(self):
        Source.objects.all().update(enabled=False)
        self.source = Source.objects.create(name='Synthetic feed', url='https://example.test/', feed_url='https://example.test/rss', enabled=True)

    def test_seeded_publishers(self):
        self.assertEqual(Source.objects.exclude(pk=self.source.pk).count(), 7)

    def test_idempotent_and_preserves_reviewed_content(self):
        scan = scan_source(self.source.pk, lambda url: RSS)
        self.assertEqual((scan.status, scan.created_count), ('success', 1))
        issue = Issue.objects.get()
        self.assertEqual(issue.current_version.severity, 'unknown')
        self.assertEqual(issue.current_version.remediation, '')
        self.assertIsNotNone(issue.current_version.published_at)
        user = get_user_model().objects.create_user('synthetic-editor')
        create_version(issue=issue, expected_version_id=issue.current_version_id, content={'remediation': 'Reviewed synthetic action'}, actor=user, change_reason='Synthetic review')
        second = scan_source(self.source.pk, lambda url: RSS.replace(b'Unverified publisher excerpt', b'Updated text'))
        self.assertEqual(second.created_count, 0)
        issue.refresh_from_db()
        self.assertEqual(issue.current_version.remediation, 'Reviewed synthetic action')
        self.assertEqual(issue.current_version.description, 'Updated text')
        self.assertEqual(issue.versions.get(version_number=1).description, 'Unverified publisher excerpt')
        self.assertEqual(issue.current_version.origin, 'automated_proposal')
        self.assertEqual(issue.versions.count(), 3)
        scan_source(self.source.pk, lambda url: RSS.replace(b'Unverified publisher excerpt', b'Updated text'))
        self.assertEqual(issue.versions.count(), 3)
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
        with patch('news.management.commands.scan_news.close_old_connections') as close_idle, patch('news.management.commands.scan_news.scan_source') as scan:
            with self.assertRaises(CommandError):
                call_command('scan_news')
            scan.assert_not_called()
            close_idle.assert_not_called()
        user = get_user_model().objects.create_user('synthetic')
        Baseline.objects.create(version='synthetic', created_by=user, snapshot={}, coverage_gaps='Synthetic only', approved_by=user, approved_at=timezone.now())
        with patch('news.management.commands.scan_news.scan_source') as scan:
            scan.return_value = Scan(status='success', created_count=0)
            call_command('scan_news', stdout=StringIO())
            scan.assert_called_once_with(self.source.pk)

    def test_review_requires_guidance_and_no_self_duplicate(self):
        scan_source(self.source.pk, lambda url: RSS)
        issue = Issue.objects.get()
        review = Review(issue=issue, issue_version=issue.current_version, decision='add', rationale='Synthetic test')
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
        data = {'issue': issue.pk, 'issue_version': issue.current_version_id, 'decision': 'ignore', 'rationale': 'Synthetic unrelated report', '_save': 'Save'}
        self.assertEqual(client.post(path, data).status_code, 403)
        for origin in ['null', 'https://foreign.test']:
            self.assertEqual(client.post(path, {**data, 'csrfmiddlewaretoken': token}, HTTP_ORIGIN=origin).status_code, 403)
        self.assertEqual(client.post(path, {**data, 'csrfmiddlewaretoken': token}, HTTP_ORIGIN='http://testserver').status_code, 302)
        review = Review.objects.get()
        self.assertEqual(review.actor, user)
        self.assertEqual(review.issue_snapshot['severity'], 'unknown')
        create_version(issue=issue, expected_version_id=issue.current_version_id, content={'severity': 'high'}, actor=user, change_reason='Synthetic severity update')
        review.refresh_from_db()
        self.assertEqual(review.issue_snapshot['severity'], 'unknown')
        self.assertEqual(client.post(f'/admin/news/review/{review.pk}/change/', {**data, 'csrfmiddlewaretoken': token}).status_code, 403)
        self.assertEqual(client.post(f'/admin/news/issue/{issue.pk}/delete/', {'csrfmiddlewaretoken': token}).status_code, 403)


class VersioningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('version-editor', password='synthetic-password')
        self.source = Source.objects.create(name='Synthetic original', url='https://example.test/', feed_url='https://example.test/rss')
        self.other_source = Source.objects.create(name='Synthetic second publisher', url='https://second.test/', feed_url='https://second.test/rss')
        scan_source(self.source.pk, lambda url: RSS)
        self.issue = Issue.objects.get()
        self.first = self.issue.current_version

    def edit(self, **kwargs):
        return create_version(issue=self.issue, expected_version_id=self.issue.current_version_id,
                              content={'severity': 'high'}, actor=self.user, change_reason='Synthetic new advisory', **kwargs)

    def test_full_snapshot_cross_source_provenance_and_history(self):
        second = self.edit(references=[{'source_id': self.other_source.pk, 'source_url': 'https://second.test/advisory', 'notes': 'Independent synthetic advisory'}])
        self.assertEqual(second.version_number, 2)
        self.assertEqual(second.name, self.first.name)
        self.assertEqual(second.created_by, self.user)
        self.assertEqual(second.origin, 'consultant_edit')
        ref = second.references.get()
        self.assertEqual(ref.source_id, self.other_source.pk)
        self.assertEqual(ref.source_name, 'Synthetic second publisher')
        self.other_source.name = 'Renamed publisher'
        self.other_source.save()
        ref.refresh_from_db()
        self.assertEqual(ref.source_name, 'Synthetic second publisher')
        self.first.refresh_from_db()
        self.assertEqual(self.first.severity, 'unknown')
        self.assertEqual(self.first.references.get().source, self.source)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.source, self.source)
        self.assertEqual(self.issue.current_version, second)

    def test_no_op_and_stale_edits(self):
        same = create_version(issue=self.issue, expected_version_id=self.first.pk, content={}, actor=self.user, change_reason='No substantive change')
        self.assertEqual(same.pk, self.first.pk)
        second = self.edit()
        with self.assertRaises(ValidationError):
            self.edit()
        self.assertEqual(self.issue.versions.count(), 2)
        self.assertEqual(second.version_number, 2)

    def test_failed_reference_validation_rolls_back_version_and_pointer(self):
        with self.assertRaises(ValidationError):
            self.edit(references=[{'source_id': self.other_source.pk, 'source_url': 'http://second.test/insecure'}])
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.current_version_id, self.first.pk)
        self.assertEqual(self.issue.versions.count(), 1)
        self.assertEqual(IssueVersionReference.objects.count(), 1)

    def test_saved_versions_and_references_reject_model_and_queryset_mutations(self):
        ref = self.first.references.get()
        for obj in [self.first, ref]:
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).delete()
        with self.assertRaises(ValidationError):
            IssueVersion.objects.filter(pk=self.first.pk).update(severity='critical')
        with self.assertRaises(ValidationError):
            IssueVersionReference.objects.create(version=self.first, source=self.other_source, source_url='https://second.test/later')

    def test_database_guards_block_raw_mutations_and_late_references(self):
        from django.db import connection, IntegrityError, transaction
        ref = self.first.references.get()
        statements = [
            ('UPDATE news_issueversion SET severity = %s WHERE id = %s', ['critical', self.first.pk]),
            ('DELETE FROM news_issueversion WHERE id = %s', [self.first.pk]),
            ('UPDATE news_issueversionreference SET notes = %s WHERE id = %s', ['altered', ref.pk]),
            ('DELETE FROM news_issueversionreference WHERE id = %s', [ref.pk]),
            ('UPDATE news_issue SET current_version_id = NULL WHERE id = %s', [self.issue.pk]),
        ]
        for sql, params in statements:
            with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql, params)
        with self.assertRaises(IntegrityError), transaction.atomic():
            IssueVersionReference.objects.bulk_create([IssueVersionReference(version=self.first, source=self.other_source, source_name='Second', source_website='https://second.test/', source_url='https://second.test/late')])
        self.first.refresh_from_db()
        self.assertEqual(self.first.severity, 'unknown')

    def test_database_rejects_backwards_current_pointer(self):
        from django.db import IntegrityError, transaction
        self.edit()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Issue.objects.filter(pk=self.issue.pk).update(current_version_id=self.first.pk)

    def test_reviews_are_specific_to_version_and_new_content_needs_review(self):
        review = Review.objects.create(issue=self.issue, issue_version=self.first, decision='ignore', rationale='Synthetic initial decision', actor=self.user, issue_snapshot={'severity': 'unknown'})
        self.assertEqual(self.issue.review_status(), 'ignore')
        second = self.edit()
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.review_status(), 'Needs review')
        review.refresh_from_db()
        self.assertEqual(review.issue_version_id, self.first.pk)
        self.assertEqual(review.issue_snapshot, {'severity': 'unknown'})
        stale = Review(issue=self.issue, issue_version=self.first, decision='ignore', rationale='Stale', actor=self.user)
        with self.assertRaises(ValidationError):
            stale.clean()
        current = Review(issue=self.issue, issue_version=second, decision='ignore', rationale='Current', actor=self.user)
        current.clean()

    def test_admin_stale_form_is_rejected_without_partial_version(self):
        self.client.force_login(self.user)
        path = f'/admin/news/issueversion/add/?issue={self.issue.pk}&base_version={self.first.pk}'
        data = {field: getattr(self.first, field) or '' for field in CONTENT_FIELDS}
        data.update(issue=self.issue.pk, base_version=self.first.pk, change_reason='Synthetic stale edit', inherit_references='on',
                    **{'references-TOTAL_FORMS': '0', 'references-INITIAL_FORMS': '0', 'references-MIN_NUM_FORMS': '0', 'references-MAX_NUM_FORMS': '1000'})
        self.edit()
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This issue changed while you were editing')
        self.assertEqual(self.issue.versions.count(), 2)

    def test_admin_no_op_does_not_create_version_or_false_addition_log(self):
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType
        self.client.force_login(self.user)
        data = {field: getattr(self.first, field) or '' for field in CONTENT_FIELDS if field != 'published_at'}
        data.update(issue=self.issue.pk, base_version=self.first.pk, change_reason='No change', inherit_references='on',
                    published_at_0=self.first.published_at.strftime('%Y-%m-%d'), published_at_1=self.first.published_at.strftime('%H:%M:%S'),
                    **{'references-TOTAL_FORMS': '0', 'references-INITIAL_FORMS': '0', 'references-MIN_NUM_FORMS': '0', 'references-MAX_NUM_FORMS': '1000'})
        response = self.client.post(f'/admin/news/issueversion/add/?issue={self.issue.pk}', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.issue.versions.count(), 1)
        self.assertFalse(LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(IssueVersion)).exists())

    def test_publisher_updates_keep_consultant_fields_and_other_references(self):
        self.edit(references=[{'source_id': self.other_source.pk, 'source_url': 'https://second.test/advisory'}])
        scan_source(self.source.pk, lambda url: RSS.replace(b'Unverified publisher excerpt', b'Publisher updated description'))
        self.issue.refresh_from_db()
        latest = self.issue.current_version
        self.assertEqual(latest.severity, 'high')
        self.assertEqual(latest.origin, 'automated_proposal')
        self.assertEqual(latest.references.count(), 2)
        self.assertTrue(latest.references.filter(source=self.other_source).exists())


from unittest import skipUnless
from django.db import connection
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'Concurrent row-lock behavior requires PostgreSQL; covered in PostgreSQL CI.')
class VersionConcurrencyTests(TransactionTestCase):
    def test_two_editors_cannot_publish_from_the_same_base(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        source = Source.objects.create(name='Synthetic concurrent source', url='https://example.test/', feed_url='https://example.test/rss')
        user = get_user_model().objects.create_user('synthetic-concurrent-editor')
        scan_source(source.pk, lambda url: RSS)
        issue = Issue.objects.get()
        expected = issue.current_version_id
        barrier = Barrier(2)

        def edit(severity):
            close_old_connections()
            try:
                local = Issue.objects.get(pk=issue.pk)
                actor = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=10)
                try:
                    create_version(issue=local, expected_version_id=expected, content={'severity': severity}, actor=actor, change_reason='Synthetic concurrent judgment')
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ['high', 'critical']))
        self.assertCountEqual(results, ['saved', 'stale'])
        issue.refresh_from_db()
        self.assertEqual(issue.current_version.version_number, 2)
        self.assertEqual(issue.versions.count(), 2)


class FeedBoundaryTests(TestCase):
    setUp = IngestionTests.setUp

    @override_settings(NEWS_MAX_ISSUES_PER_SOURCE=1)
    def test_candidate_quota_preserves_existing_rows(self):
        first = scan_source(self.source.pk, lambda url: RSS)
        second = scan_source(self.source.pk, lambda url: RSS.replace(b'/advisory', b'/new-advisory'))
        self.assertEqual(first.status, 'success')
        self.assertEqual(second.status, 'failed')
        self.assertIn('Storage quota', second.error)
        self.assertEqual(Issue.objects.count(), 1)
        self.assertEqual(IssueVersion.objects.count(), 1)

    @override_settings(NEWS_MAX_AUTO_VERSIONS_PER_ISSUE=1)
    def test_automatic_version_quota_preserves_history(self):
        scan_source(self.source.pk, lambda url: RSS)
        second = scan_source(self.source.pk, lambda url: RSS.replace(b'Unverified publisher excerpt', b'Changed excerpt'))
        self.assertEqual(second.status, 'failed')
        self.assertIn('Storage quota', second.error)
        self.assertEqual(IssueVersion.objects.count(), 1)

    def test_xml_structural_limits_fail_during_parsing(self):
        for data in [b'<rss>' + b'<item/>' * 501 + b'</rss>', b'<rss>' + b'<nested>' * 65 + b'</nested>' * 65 + b'</rss>', b'<rss>' + b'<node/>' * 10001 + b'</rss>']:
            with self.assertRaises(ValueError):
                parse_feed(data)

    @override_settings(NEWS_ALLOWED_HOSTS=['publisher.test'])
    def test_direct_connection_dials_pinned_ip_with_original_tls_hostname(self):
        from .ingestion import PinnedHTTPSConnection
        from unittest.mock import Mock
        tls = Mock()
        conn = PinnedHTTPSConnection('publisher.test', context=tls)
        dial = Mock()
        conn._create_connection = dial
        with patch('news.ingestion.public_address', return_value='93.184.216.34'):
            conn.connect()
        self.assertEqual(dial.call_args.args[0], ('93.184.216.34', 443))
        self.assertEqual(tls.wrap_socket.call_args.kwargs['server_hostname'], 'publisher.test')

    @override_settings(NEWS_ALLOWED_HOSTS=['publisher.test'])
    def test_proxy_tunnels_to_pinned_ip_and_keeps_publisher_tls_verification(self):
        import http.client
        from .ingestion import PinnedHTTPSConnection
        from unittest.mock import Mock
        tls = Mock()
        conn = PinnedHTTPSConnection('proxy.test', 8080, context=tls)
        conn.set_tunnel('publisher.test', 443)
        conn._create_connection = Mock()
        tunnel_targets = []
        with patch('news.ingestion.public_address', return_value='93.184.216.34'), patch.object(http.client.HTTPConnection, '_tunnel', lambda connection: tunnel_targets.append(connection._tunnel_host)):
            conn.connect()
        self.assertEqual(tunnel_targets, ['93.184.216.34'])
        self.assertEqual(tls.wrap_socket.call_args.kwargs['server_hostname'], 'publisher.test')
        self.assertEqual(conn._create_connection.call_args.args[0], ('proxy.test', 8080))

    @override_settings(NEWS_ALLOWED_HOSTS=['publisher.test'])
    def test_rebinding_to_private_address_is_rejected_at_connect(self):
        from .ingestion import PinnedHTTPSConnection
        conn = PinnedHTTPSConnection('publisher.test')
        with patch('news.ingestion.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError):
                conn.connect()


class SourceIdentityTests(TestCase):
    def test_url_is_primary_key_and_normalized_duplicate_is_rejected(self):
        from django.db import IntegrityError, transaction
        self.assertEqual(Source._meta.pk.name, 'url')
        original = Source.objects.get(pk='https://www.cisa.gov/')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Source.objects.create(name='Duplicate CISA', url='HTTPS://WWW.CISA.GOV:443/#news', feed_url=original.feed_url)
        original.refresh_from_db()
        self.assertEqual(original.name, 'CISA')
        self.assertEqual(Source.objects.count(), 7)
        duplicate = Source(name='Another label', url='https://WWW.CISA.GOV', feed_url=original.feed_url)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_new_instance_save_cannot_overwrite_existing_source(self):
        from django.db import IntegrityError, transaction
        original = Source.objects.get(pk='https://www.cisa.gov/')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Source(name='Silent overwrite', url=original.pk, feed_url=original.feed_url).save()
        original.refresh_from_db()
        self.assertEqual(original.name, 'CISA')

    def test_requested_seeds_are_idempotent_and_keep_customizations(self):
        import importlib
        from django.apps import apps
        from django.db import connection
        seed = importlib.import_module('news.migrations.0006_add_requested_sources').seed
        source = Source.objects.get(pk='https://www.upguard.com/blog')
        source.notes = 'Consultant configuration must survive seeding'
        source.save()
        for _ in range(2):
            seed(apps, connection.schema_editor())
        source.refresh_from_db()
        self.assertEqual(Source.objects.count(), 7)
        self.assertEqual(source.notes, 'Consultant configuration must survive seeding')
        self.assertSetEqual(set(Source.objects.filter(url__in=['https://www.cisa.gov/', 'https://www.upguard.com/blog', 'https://www.schneier.com/', 'https://www.securityweek.com/']).values_list('name', flat=True)), {'CISA', 'UpGuard', 'Schneier on Security', 'SecurityWeek'})

    def test_names_are_labels_and_url_identity_is_permanent(self):
        source = Source.objects.get(pk='https://www.cisa.gov/')
        Source.objects.create(name=source.name, url='https://alternate.example.test/', feed_url=source.feed_url)
        source.url = 'https://different.example.test/'
        with self.assertRaises(ValidationError):
            source.save()
        self.assertTrue(Source.objects.filter(pk='https://www.cisa.gov/').exists())

    def test_canonical_path_and_invalid_website_urls(self):
        from .source_urls import canonical_source_url
        self.assertEqual(canonical_source_url(' HTTPS://WWW.UPGUARD.COM:443/blog/#section '), 'https://www.upguard.com/blog')
        for value in ['http://example.test/', 'https://user:secret@example.test/', 'https://example.test/?token=secret', 'https://example.test:444/']:
            with self.assertRaises(ValidationError):
                canonical_source_url(value)

    def test_admin_history_includes_legacy_numeric_identity(self):
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.admin.utils import quote
        from django.contrib.contenttypes.models import ContentType
        from django.urls import reverse
        user = get_user_model().objects.create_superuser('synthetic-source-auditor', password='synthetic-password')
        source = Source.objects.get(pk='https://www.cisa.gov/')
        # Seeded after the key migration, so emulate a retained legacy mapping.
        source.legacy_id = 9001
        source.save()
        LogEntry.objects.create(user=user, content_type=ContentType.objects.get_for_model(Source), object_id='9001', object_repr='Original source label', action_flag=CHANGE, change_message='Synthetic legacy source edit')
        self.client.force_login(user)
        response = self.client.get(reverse('admin:news_source_history', args=[quote(source.pk)]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Synthetic legacy source edit')
        self.assertContains(self.client.get(reverse('admin:news_source_change', args=[quote(source.pk)])), 'https://www.cisa.gov/')


class AutomaticScanConfigurationTests(TestCase):
    @override_settings(NEWS_AUTO_SCAN_ENABLED=False)
    def test_disabled_worker_does_not_access_database_or_fetch_feeds(self):
        output = StringIO()
        with patch('news.management.commands.scan_news.time.sleep', side_effect=KeyboardInterrupt), patch('news.management.commands.scan_news.scan_source') as scan:
            with self.assertNumQueries(0), self.assertRaises(KeyboardInterrupt):
                call_command('scan_news', loop=True, stdout=output)
        scan.assert_not_called()
        self.assertIn('Automatic news scanning is disabled', output.getvalue())

    @override_settings(NEWS_AUTO_SCAN_ENABLED=True)
    def test_enabled_worker_retains_baseline_gate(self):
        output = StringIO()
        with patch('news.management.commands.scan_news.time.sleep', side_effect=KeyboardInterrupt), patch('news.management.commands.scan_news.scan_source') as scan:
            with self.assertRaises(KeyboardInterrupt):
                call_command('scan_news', loop=True, stdout=output)
        scan.assert_not_called()
        self.assertIn('Waiting for an approved baseline', output.getvalue())

    @override_settings(NEWS_AUTO_SCAN_ENABLED=True)
    def test_enabled_worker_scans_only_enabled_sources(self):
        user = get_user_model().objects.create_user('synthetic-auto-scanner')
        Baseline.objects.create(version='synthetic-auto', created_by=user, snapshot={}, coverage_gaps='Synthetic', approved_by=user, approved_at=timezone.now())
        Source.objects.all().update(enabled=False)
        source = Source.objects.get(pk='https://www.cisa.gov/')
        source.enabled = True
        source.save()
        with patch('news.management.commands.scan_news.time.sleep', side_effect=KeyboardInterrupt), patch('news.management.commands.scan_news.scan_source') as scan:
            scan.return_value = Scan(status='success', created_count=0)
            with self.assertRaises(KeyboardInterrupt):
                call_command('scan_news', loop=True, stdout=StringIO())
        scan.assert_called_once_with(source.pk)

    @override_settings(NEWS_AUTO_SCAN_ENABLED=False)
    def test_manual_scan_remains_available_while_automatic_scanning_is_off(self):
        user = get_user_model().objects.create_user('synthetic-manual-scanner')
        Baseline.objects.create(version='synthetic-manual', created_by=user, snapshot={}, coverage_gaps='Synthetic', approved_by=user, approved_at=timezone.now())
        with patch('news.management.commands.scan_news.scan_source') as scan:
            scan.return_value = Scan(status='success', created_count=0)
            call_command('scan_news', stdout=StringIO())
        self.assertEqual(scan.call_count, Source.objects.filter(enabled=True).count())
