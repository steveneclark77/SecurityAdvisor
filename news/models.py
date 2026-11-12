from django.conf import settings
from django.db import models


class Source(models.Model):
    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(max_length=1000)
    feed_url = models.URLField(max_length=1000, help_text='HTTPS RSS or Atom endpoint; its host must be allowed in NEWS_ALLOWED_HOSTS.')
    notes = models.TextField(blank=True)
    enabled = models.BooleanField(default=True, help_text='Disable instead of deleting historical sources.')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        from urllib.parse import urlsplit
        try:
            parts = urlsplit(self.feed_url)
            valid = parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password and parts.port in (None, 443)
        except ValueError:
            valid = False
        if not valid:
            raise ValidationError({'feed_url': 'Use a credential-free HTTPS feed URL on port 443.'})
        if parts.hostname not in settings.NEWS_ALLOWED_HOSTS:
            raise ValidationError({'feed_url': 'Add this publisher host to NEWS_ALLOWED_HOSTS before enabling its feed.'})

    def __str__(self):
        return self.name


class Scan(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='scans')
    feed_url = models.URLField(max_length=1000)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default='running')
    created_count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)


class Issue(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='issues')
    first_scan = models.ForeignKey(Scan, on_delete=models.PROTECT)
    identity = models.CharField(max_length=64)
    discovered_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    current_version = models.OneToOneField('IssueVersion', null=True, blank=True, on_delete=models.PROTECT, related_name='+', editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'identity'], name='unique_source_news_identity')]
        ordering = ['-discovered_at']

    def __str__(self):
        return self.current_version.name if self.current_version_id else f'Issue {self.pk}'

    @property
    def name(self):
        return str(self)

    def review_status(self):
        review = self.reviews.filter(issue_version_id=self.current_version_id).order_by('-created_at', '-pk').first()
        return review.decision if review else 'Needs review'


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Saved issue versions and references are immutable.')

    def delete(self):
        from django.core.exceptions import ValidationError
        raise ValidationError('Saved issue versions and references cannot be deleted.')


class ImmutableRecord(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if not self._state.adding:
            raise ValidationError('Saved issue versions and references are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Saved issue versions and references cannot be deleted.')


class IssueVersion(ImmutableRecord):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='versions')
    version_number = models.PositiveIntegerField()
    name = models.CharField(max_length=500)
    url = models.URLField(max_length=2000)
    description = models.TextField(blank=True, help_text='Publisher feed excerpt, not independently verified.')
    published_at = models.DateTimeField(null=True, blank=True)
    severity = models.CharField(max_length=20, default='unknown', choices=[(x, x.title()) for x in ['unknown', 'informational', 'low', 'medium', 'high', 'critical']])
    kind = models.CharField(max_length=30, default='unclassified', choices=[(x, x.replace('_', ' ').title()) for x in ['unclassified', 'vulnerability', 'best_practice', 'remediation', 'other']])
    remediation = models.TextField(blank=True, help_text='Consultant-reviewed actions; blank means not established.')
    identifiers = models.TextField(blank=True, help_text='CVE/CWE/product/version references, one per line.')
    origin = models.CharField(max_length=30, choices=[(x, x.replace('_', ' ').title()) for x in ['publisher_ingestion', 'consultant_edit', 'automated_proposal', 'legacy_migration']])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    change_reason = models.TextField()

    class Meta:
        ordering = ['-version_number']
        constraints = [models.UniqueConstraint(fields=['issue', 'version_number'], name='unique_issue_version_number'), models.CheckConstraint(condition=models.Q(version_number__gte=1), name='positive_issue_version')]

    def __str__(self):
        return f'{self.name} · v{self.version_number}'


class IssueVersionReference(ImmutableRecord):
    version = models.ForeignKey(IssueVersion, on_delete=models.PROTECT, related_name='references')
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    source_name = models.CharField(max_length=200, editable=False)
    source_website = models.URLField(max_length=1000, editable=False)
    source_url = models.URLField(max_length=2000)
    source_published_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['version', 'source_url'], name='unique_version_reference_url')]

    def clean(self):
        from .ingestion import validate_url
        from django.core.exceptions import ValidationError
        try:
            validate_url(self.source_url)
        except ValueError as exc:
            raise ValidationError({'source_url': str(exc)}) from exc

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        current = self.version.issue.current_version
        if current and self.version.version_number <= current.version_number:
            raise ValidationError('References of a published issue version are immutable.')
        if not self.source_name:
            self.source_name = self.source.name
            self.source_website = self.source.url
        return super().save(*args, **kwargs)


class Review(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='reviews')
    issue_version = models.ForeignKey(IssueVersion, null=True, blank=True, on_delete=models.PROTECT, help_text='Legacy reviews without an exact version retain their original snapshot.')
    decision = models.CharField(max_length=20, choices=[(x, x.title()) for x in ['add', 'update', 'ignore']])
    rationale = models.TextField()
    proposed_guidance = models.TextField(blank=True)
    controls = models.ManyToManyField('library.Control', blank=True, help_text='Related working controls; no automatic changes are applied.')
    duplicate_of = models.ForeignKey(Issue, on_delete=models.PROTECT, null=True, blank=True, related_name='related_reviews')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    issue_snapshot = models.JSONField(default=dict, editable=False)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.issue_version_id and self.issue_version.issue_id != self.issue_id:
            raise ValidationError('The reviewed version must belong to this issue.')
        if self._state.adding and (not self.issue_version_id or self.issue_version_id != self.issue.current_version_id):
            raise ValidationError('Select the current issue version; reload if it has changed.')
        if self.duplicate_of_id and self.duplicate_of_id == self.issue_id:
            raise ValidationError('An issue cannot duplicate itself.')
        if self.decision in ['add', 'update'] and not self.proposed_guidance.strip():
            raise ValidationError('Add/update decisions require proposed guidance.')
