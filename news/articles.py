"""Capture public publisher observations without changing accepted issue content."""
import hashlib
import json
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Article, ArticleRevision


def content_hash(title, text, published_at):
    return hashlib.sha256(json.dumps([title, text, published_at.isoformat() if published_at else None], ensure_ascii=False).encode()).hexdigest()


@transaction.atomic
def capture_article(source, scan, entry):
    from .ingestion import IngestionQuotaExceeded
    article, created = Article.objects.get_or_create(source=source, identity=entry['identity'],
        defaults={'url':entry['url'], 'first_scan':scan, 'last_seen_at':timezone.now()})
    if created and Article.objects.filter(source=source).count() > settings.NEWS_MAX_ISSUES_PER_SOURCE:
        raise IngestionQuotaExceeded('Publisher article quota reached.')
    digest = content_hash(entry['name'], entry['description'], entry['published_at'])
    revision = article.revisions.filter(content_hash=digest).first()
    if revision is None:
        if article.revisions.count() >= settings.NEWS_MAX_AUTO_VERSIONS_PER_ISSUE:
            raise IngestionQuotaExceeded('Publisher article revision quota reached.')
        revision = ArticleRevision.objects.create(article=article, title=entry['name'], text=entry['description'],
            published_at=entry['published_at'], content_hash=digest,
            source_name=source.name, source_website=source.url)
    Article.objects.filter(pk=article.pk).update(last_seen_at=timezone.now(), current_revision=revision)
    return created
