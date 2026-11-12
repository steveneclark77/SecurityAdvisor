"""Exercise legacy data on an isolated SQLite database, never the configured DB."""
import os
import subprocess
import sys
from django.test import SimpleTestCase


class LegacyMigrationTests(SimpleTestCase):
    def test_existing_issue_and_review_are_preserved(self):
        script = r'''
import os
import tempfile
os.environ['DATABASE_ENGINE'] = 'sqlite'
os.environ['DJANGO_SECRET_KEY'] = 'synthetic-migration-test'
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
with tempfile.TemporaryDirectory(prefix='synthetic-news-migration-') as folder:
    settings.DATABASES['default']['NAME'] = folder + '/migration.sqlite3'
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    target = [('news', '0002_seed_sources')]
    executor.migrate(target)
    apps = executor.loader.project_state(target).apps
    User = apps.get_model('auth', 'User')
    Source = apps.get_model('news', 'Source')
    Scan = apps.get_model('news', 'Scan')
    Issue = apps.get_model('news', 'Issue')
    Review = apps.get_model('news', 'Review')
    from django.utils import timezone
    user = User.objects.create(username='synthetic-migration-reviewer')
    source = Source.objects.get(name='The Hacker News')
    scan = Scan.objects.create(source=source, feed_url=source.feed_url)
    issue = Issue.objects.create(source=source, first_scan=scan, identity='synthetic-legacy', name='Legacy title', url='https://example.test/legacy', description='Legacy excerpt', severity='high', remediation='Legacy recommendation', identifiers='CVE-SYNTHETIC', kind='vulnerability', last_seen_at=timezone.now())
    old_snapshot = {'name': 'Earlier title', 'severity': 'low', 'remediation': 'Earlier recommendation'}
    review = Review.objects.create(issue=issue, actor=user, decision='ignore', rationale='Historical rationale', issue_snapshot=old_snapshot)
    issue_id, review_id = issue.pk, review.pk
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())
    from news.models import Issue, Review
    migrated = Issue.objects.get(pk=issue_id)
    version = migrated.current_version
    assert version.version_number == 1
    assert version.name == 'Legacy title'
    assert version.remediation == 'Legacy recommendation'
    assert version.severity == 'high'
    assert version.identifiers == 'CVE-SYNTHETIC'
    assert version.origin == 'legacy_migration'
    assert version.created_by_id is None
    assert version.references.get().source_name == 'The Hacker News'
    preserved = Review.objects.get(pk=review_id)
    assert preserved.issue_snapshot == old_snapshot
    assert preserved.issue_version_id is None
    assert preserved.rationale == 'Historical rationale'
    from django.db.migrations.exceptions import IrreversibleError
    try:
        MigrationExecutor(connection).migrate(target)
    except IrreversibleError:
        pass
    else:
        raise AssertionError('Downgrade must not flatten history or remove its guards')
    from django.db import IntegrityError
    try:
        with connection.cursor() as cursor:
            cursor.execute('UPDATE news_issueversion SET severity = %s WHERE id = %s', ['low', version.pk])
    except IntegrityError:
        pass
    else:
        raise AssertionError('Failed downgrade must retain immutability guards')
    connection.close()
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=os.getcwd(), capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
