from django.db import migrations


SOURCES = [
    ('CISA', 'https://www.cisa.gov/', 'https://www.cisa.gov/cybersecurity-advisories/all.xml'),
    ('UpGuard', 'https://www.upguard.com/blog', 'https://www.upguard.com/blog/rss.xml'),
    ('Schneier on Security', 'https://www.schneier.com/', 'https://www.schneier.com/feed/atom/'),
    ('SecurityWeek', 'https://www.securityweek.com/', 'https://www.securityweek.com/feed/'),
]


def seed(apps, schema_editor):
    Source = apps.get_model('news', 'Source')
    for name, url, feed_url in SOURCES:
        Source.objects.using(schema_editor.connection.alias).get_or_create(url=url, defaults={
            'name': name, 'feed_url': feed_url, 'notes': 'Requested publisher feed. Verify availability and reuse terms. Store excerpts and links only; review every candidate.'})


class Migration(migrations.Migration):
    dependencies = [('news', '0005_source_url_primary_key')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
