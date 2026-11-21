import hashlib
import json
from django.db import migrations

TABLES = ['news_articlerevision','news_analysisresult','news_issueproposal','news_proposaldecision','news_issuearticlelink']


def backfill(apps, schema_editor):
    Issue = apps.get_model('news','Issue')
    Article = apps.get_model('news','Article')
    Revision = apps.get_model('news','ArticleRevision')
    Link = apps.get_model('news','IssueArticleLink')
    for issue in Issue.objects.select_related('source').iterator():
        for version in issue.versions.filter(origin__in=['publisher_ingestion','automated_proposal','legacy_migration']).order_by('version_number').iterator():
            identity = hashlib.sha256(version.url.encode()).hexdigest()
            article, _ = Article.objects.get_or_create(source_id=issue.source_id, identity=identity,
                defaults={'url':version.url,'first_scan_id':issue.first_scan_id,'last_seen_at':issue.last_seen_at})
            digest = hashlib.sha256(json.dumps([version.name,version.description,version.published_at.isoformat() if version.published_at else None],ensure_ascii=False).encode()).hexdigest()
            historical_reference=version.references.filter(source_id=issue.source_id,source_url=version.url).first()
            revision, _ = Revision.objects.get_or_create(article=article, content_hash=digest,
                defaults={'title':version.name,'text':version.description,'published_at':version.published_at,
                    'source_name':historical_reference.source_name if historical_reference else issue.source.name,
                    'source_website':historical_reference.source_website if historical_reference else issue.source_id})
            Link.objects.create(issue=issue, revision=revision, relationship='supports', rationale='Preserved pre-analysis publisher association; not an automated match judgment.')


def install(apps, schema_editor):
    if schema_editor.connection.vendor == 'sqlite':
        for table in TABLES:
            for action in ['UPDATE','DELETE']:
                schema_editor.execute(f"CREATE TRIGGER {table}_immutable_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Analysis history is immutable'); END")
    elif schema_editor.connection.vendor == 'postgresql':
        for table in TABLES:
            schema_editor.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION news_immutable()')
    else:
        raise RuntimeError('Analysis history requires SQLite or PostgreSQL.')


def uninstall(apps, schema_editor):
    """Only for synthetic test database teardown; migration is not reversible."""
    for table in TABLES:
        if schema_editor.connection.vendor == 'sqlite':
            for action in ['update','delete']:
                schema_editor.execute(f'DROP TRIGGER {table}_immutable_{action}')
        elif schema_editor.connection.vendor == 'postgresql':
            schema_editor.execute(f'DROP TRIGGER {table}_immutable ON {table}')


class Migration(migrations.Migration):
    dependencies = [('news','0007_analysisbudget_analysisrun_analysisresult_article_and_more')]
    operations = [migrations.RunPython(backfill), migrations.RunPython(install)]
