"""Move source foreign keys by value before replacing the numeric primary key."""
import importlib
from urllib.parse import quote, urlsplit, urlunsplit
from django.db import migrations, models
import django.db.models.deletion


def prepare(apps, schema_editor):
    Source = apps.get_model('news', 'Source')
    alias = schema_editor.connection.alias
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')
    seen, rows = {}, []
    for source in Source.objects.using(alias).all():
        try:
            parts = urlsplit(source.url.strip())
            if parts.scheme.lower() != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443) or parts.query:
                raise ValueError
            hostname = parts.hostname.encode('idna').decode('ascii').lower()
            hostname = f'[{hostname}]' if ':' in hostname else hostname
            url = urlunsplit(('https', hostname, quote(parts.path.rstrip('/') or '/', safe="/:@!$&'()*+,;=-._~%"), '', ''))
            if len(url) > 1000:
                raise ValueError
        except (ValueError, UnicodeError, AttributeError) as exc:
            raise RuntimeError(f'Source {source.pk} has an invalid website identity. Correct it before retrying; no records have been merged or deleted.') from exc
        if url in seen:
            raise RuntimeError(f'Sources {seen[url]} and {source.pk} have the same canonical website URL. Resolve duplicates while preserving their history before retrying; no sources were merged or deleted.')
        seen[url] = source.pk
        rows.append((source.pk, url))
    for pk, url in rows:
        Source.objects.using(alias).filter(pk=pk).update(url=url, legacy_id=pk)


def guards():
    return importlib.import_module('news.migrations.0004_version_immutability')


def suspend(apps, schema_editor):
    # DDL and the complete FK rewrite are in one atomic migration. The updater
    # stops both writers; PostgreSQL also locks history tables until commit.
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('LOCK TABLE news_issue, news_issueversion, news_issueversionreference IN ACCESS EXCLUSIVE MODE')
    guards().uninstall(apps, schema_editor)


def copy_links(apps, schema_editor):
    alias = schema_editor.connection.alias
    mapping = dict(apps.get_model('news', 'Source').objects.using(alias).values_list('id', 'url'))
    for name in ['Scan', 'Issue', 'IssueVersionReference']:
        Model = apps.get_model('news', name)
        for pk, old_source_id in Model.objects.using(alias).values_list('pk', 'source_id').iterator():
            Model.objects.using(alias).filter(pk=pk).update(source_by_url=mapping[old_source_id])


def restore(apps, schema_editor):
    guards().install(apps, schema_editor)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('news', '0004_version_immutability')]
    operations = [
        migrations.AddField(model_name='source', name='legacy_id', field=models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)),
        migrations.RunPython(prepare),
        migrations.RunPython(suspend),
        migrations.AlterField(model_name='source', name='url', field=models.URLField(max_length=1000, unique=True)),
        migrations.AlterField(model_name='source', name='name', field=models.CharField(max_length=200)),
        # Stage URL values in plain columns so no FK depends on the old URL
        # unique index when PostgreSQL replaces that index with the primary key.
        migrations.AddField(model_name='scan', name='source_by_url', field=models.CharField(max_length=1000, null=True)),
        migrations.AddField(model_name='issue', name='source_by_url', field=models.CharField(max_length=1000, null=True)),
        migrations.AddField(model_name='issueversionreference', name='source_by_url', field=models.CharField(max_length=1000, null=True)),
        migrations.RunPython(copy_links),
        migrations.RemoveConstraint(model_name='issue', name='unique_source_news_identity'),
        migrations.RemoveField(model_name='scan', name='source'),
        migrations.RemoveField(model_name='issue', name='source'),
        migrations.RemoveField(model_name='issueversionreference', name='source'),
        migrations.RemoveField(model_name='source', name='id'),
        migrations.AlterField(model_name='source', name='url', field=models.URLField(max_length=1000, primary_key=True, serialize=False)),
        migrations.RenameField(model_name='scan', old_name='source_by_url', new_name='source'),
        migrations.RenameField(model_name='issue', old_name='source_by_url', new_name='source'),
        migrations.RenameField(model_name='issueversionreference', old_name='source_by_url', new_name='source'),
        migrations.AlterField(model_name='scan', name='source', field=models.ForeignKey(to='news.source', related_name='scans', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AlterField(model_name='issue', name='source', field=models.ForeignKey(to='news.source', related_name='issues', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AlterField(model_name='issueversionreference', name='source', field=models.ForeignKey(to='news.source', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddConstraint(model_name='issue', constraint=models.UniqueConstraint(fields=['source', 'identity'], name='unique_source_news_identity')),
        migrations.RunPython(restore),
    ]
