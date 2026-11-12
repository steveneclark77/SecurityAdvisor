from django.db import migrations


def seed(apps, schema_editor):
    Source = apps.get_model('news', 'Source')
    for name, url, feed in [
        ('The Hacker News', 'https://thehackernews.com/', 'https://feeds.feedburner.com/TheHackersNews'),
        ('Bleeping Computer', 'https://www.bleepingcomputer.com/', 'https://www.bleepingcomputer.com/feed/'),
        ('Dark Reading', 'https://www.darkreading.com/', 'https://www.darkreading.com/rss.xml'),
    ]:
        Source.objects.using(schema_editor.connection.alias).get_or_create(name=name, defaults={
            'url': url, 'feed_url': feed,
            'notes': 'Initial publisher feed. Verify current feed availability and reuse terms. Store excerpts and links only; review every candidate.'})


class Migration(migrations.Migration):
    dependencies = [('news', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
