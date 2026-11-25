from django.conf import settings
from django.db import models


class Source(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=1000, primary_key=True)
    legacy_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True, editable=False)
    feed_url = models.URLField(max_length=1000, help_text='HTTPS RSS or Atom endpoint; its host must be allowed in NEWS_ALLOWED_HOSTS.')
    notes = models.TextField(blank=True)
    enabled = models.BooleanField(default=True, help_text='Disable instead of deleting historical sources.')
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._original_url = instance.pk
        return instance

    def save(self, *args, **kwargs):
        from .source_urls import canonical_source_url
        from django.core.exceptions import ValidationError
        self.url = canonical_source_url(self.url)
        if not self._state.adding and self.url != self._original_url:
            raise ValidationError('A source website URL is its permanent identity; create a separate source for a different website.')
        if self._state.adding:
            kwargs['force_insert'] = True
        result = super().save(*args, **kwargs)
        self._original_url = self.url
        return result

    def clean(self):
        from django.core.exceptions import ValidationError
        from urllib.parse import urlsplit
        from .source_urls import canonical_source_url
        try:
            self.url = canonical_source_url(self.url)
        except ValidationError as exc:
            raise ValidationError({"url": exc.messages}) from exc
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


class Article(models.Model):
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='articles')
    url = models.URLField(max_length=2000)
    identity = models.CharField(max_length=64)
    first_scan = models.ForeignKey(Scan, on_delete=models.PROTECT)
    current_revision = models.ForeignKey('ArticleRevision', on_delete=models.PROTECT, null=True, blank=True, related_name='+', editable=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'identity'], name='unique_source_article')]

    def __str__(self):
        return f'{self.source}: {self.url}'


class ArticleRevision(ImmutableRecord):
    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name='revisions')
    title = models.CharField(max_length=500)
    text = models.TextField()
    published_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64)
    source_name = models.CharField(max_length=200)
    source_website = models.URLField(max_length=1000)

    class Meta:
        ordering = ['-pk']
        constraints = [models.UniqueConstraint(fields=['article', 'content_hash'], name='unique_article_content')]

    def __str__(self):
        return self.title


class AnalysisRun(models.Model):
    revision = models.ForeignKey(ArticleRevision, on_delete=models.PROTECT, related_name='analysis_runs')
    policy_key = models.CharField(max_length=64)
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=30)
    schema_version = models.CharField(max_length=30)
    attempt = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, default='queued', choices=[(x,x.title()) for x in ['queued','running','succeeded','failed']])
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=300, blank=True)
    input_snapshot = models.JSONField(default=dict)
    reserved_cents = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision','policy_key','attempt'], name='unique_analysis_attempt')]

    def __str__(self):
        return f'Analysis {self.pk}: {self.status}'


class AnalysisBudget(models.Model):
    day = models.DateField(primary_key=True)
    reserved_cents = models.PositiveIntegerField(default=0)


class AnalysisResult(ImmutableRecord):
    run = models.OneToOneField(AnalysisRun, on_delete=models.PROTECT, related_name='result')
    output = models.JSONField()
    input_tokens = models.PositiveIntegerField()
    output_tokens = models.PositiveIntegerField()
    estimated_cost_cents = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class IssueProposal(ImmutableRecord):
    result = models.ForeignKey(AnalysisResult, on_delete=models.PROTECT, related_name='proposals')
    position = models.PositiveSmallIntegerField()
    target_issue = models.ForeignKey(Issue, on_delete=models.PROTECT, null=True, blank=True)
    base_version = models.ForeignKey(IssueVersion, on_delete=models.PROTECT, null=True, blank=True)
    content = models.JSONField()
    matching = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['result','position'], name='unique_result_proposal')]

    def __str__(self):
        return f'Proposal {self.pk}: {self.content.get("name", "")}'


class ProposalDecision(ImmutableRecord):
    proposal = models.OneToOneField(IssueProposal, on_delete=models.PROTECT, related_name='decision')
    decision = models.CharField(max_length=20, choices=[('accept','Accept'),('reject','Reject'),('supersede','Supersede')])
    rationale = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    issue_version = models.ForeignKey(IssueVersion, on_delete=models.PROTECT, null=True, blank=True)
    content_snapshot = models.JSONField(default=dict)


class IssueArticleLink(ImmutableRecord):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='article_links')
    revision = models.ForeignKey(ArticleRevision, on_delete=models.PROTECT, related_name='issue_links')
    relationship = models.CharField(max_length=20, choices=[('supports','Supports'),('retracts','Retracts association')])
    rationale = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EmbeddingCache(ImmutableRecord):
    key = models.CharField(max_length=64, unique=True)
    model = models.CharField(max_length=100)
    content_hash = models.CharField(max_length=64)
    vector = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class EmbeddingBucket(models.Model):
    embedding = models.ForeignKey(EmbeddingCache,on_delete=models.PROTECT,related_name='buckets')
    key = models.CharField(max_length=40,db_index=True)


class EmbeddingAttempt(models.Model):
    key = models.CharField(max_length=64,db_index=True)
    status = models.CharField(max_length=20,default='running')
    model = models.CharField(max_length=100)
    content_hash = models.CharField(max_length=64)
    reserved_cents = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=300,blank=True)
    tokens = models.PositiveIntegerField(default=0)


class IssueMatchProfile(models.Model):
    issue = models.OneToOneField(Issue,on_delete=models.PROTECT,related_name='match_profile')
    source_version = models.ForeignKey(IssueVersion,on_delete=models.PROTECT)
    identity_hash = models.CharField(max_length=64,db_index=True)
    summary = models.TextField()
    fingerprint = models.JSONField()
    embedding = models.ForeignKey(EmbeddingCache,on_delete=models.PROTECT,null=True)


class IssueMatchKey(models.Model):
    profile = models.ForeignKey(IssueMatchProfile,on_delete=models.CASCADE,related_name='keys')
    kind = models.CharField(max_length=20)
    value = models.CharField(max_length=200,db_index=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['profile','kind','value'],name='unique_issue_match_key')]


class MatchComparison(ImmutableRecord):
    key = models.CharField(max_length=64,unique=True)
    issue = models.ForeignKey(Issue,on_delete=models.PROTECT)
    extraction_hash = models.CharField(max_length=64)
    identity_hash = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=30)
    features = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class CalibrationVersion(ImmutableRecord):
    name = models.CharField(max_length=200)
    policy_version = models.CharField(max_length=30)
    dataset_hash = models.CharField(max_length=64)
    label_ids = models.JSONField()
    metrics = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    def __str__(self): return self.name


class MatchingConfiguration(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    autonomous_enabled = models.BooleanField(default=False)
    active_calibration = models.ForeignKey(CalibrationVersion,on_delete=models.PROTECT,null=True,blank=True)
    catalog_generation = models.PositiveBigIntegerField(default=0,editable=False)
    index_ready_generation = models.PositiveBigIntegerField(default=0,editable=False)
    index_ready_model = models.CharField(max_length=100,blank=True,editable=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return 'Security news matching configuration'


class MatchingConfigurationEvent(ImmutableRecord):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    snapshot = models.JSONField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class MatchAssessment(ImmutableRecord):
    key = models.CharField(max_length=64,unique=True)
    proposal = models.ForeignKey(IssueProposal,on_delete=models.PROTECT,related_name='assessments')
    catalog_generation = models.PositiveBigIntegerField()
    calibration = models.ForeignKey(CalibrationVersion,on_delete=models.PROTECT,null=True)
    prediction = models.CharField(max_length=20)
    target_issue = models.ForeignKey(Issue,on_delete=models.PROTECT,null=True)
    bucket = models.CharField(max_length=200)
    confidence = models.FloatField(null=True)
    evidence = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class MatchDecision(ImmutableRecord):
    proposal = models.ForeignKey(IssueProposal,on_delete=models.PROTECT,related_name='match_decisions')
    assessment = models.ForeignKey(MatchAssessment,on_delete=models.PROTECT)
    outcome = models.CharField(max_length=20)
    issue = models.ForeignKey(Issue,on_delete=models.PROTECT,null=True)
    automatic = models.BooleanField(default=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True)
    rationale = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class MatchFeedback(ImmutableRecord):
    proposal = models.ForeignKey(IssueProposal,on_delete=models.PROTECT,related_name='match_feedback')
    assessment = models.ForeignKey(MatchAssessment,on_delete=models.PROTECT)
    decision = models.ForeignKey(MatchDecision,on_delete=models.PROTECT)
    outcome = models.CharField(max_length=20)
    correct_issue = models.ForeignKey(Issue,on_delete=models.PROTECT,null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    rationale = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class InboxEvent(ImmutableRecord):
    key = models.CharField(max_length=100,unique=True)
    kind = models.CharField(max_length=20)
    title = models.CharField(max_length=500)
    proposal = models.ForeignKey(IssueProposal,on_delete=models.PROTECT,null=True)
    issue = models.ForeignKey(Issue,on_delete=models.PROTECT,null=True)
    decision = models.ForeignKey(MatchDecision,on_delete=models.PROTECT,null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class InboxReceipt(models.Model):
    event = models.ForeignKey(InboxEvent,on_delete=models.PROTECT,related_name='receipts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    read_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['event','user'],name='unique_news_inbox_receipt')]


class DigestDelivery(models.Model):
    day = models.DateField(unique=True)
    status = models.CharField(max_length=20,default='pending')
    first_event_id = models.PositiveBigIntegerField(default=0)
    last_event_id = models.PositiveBigIntegerField(default=0)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    attempted_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=300,blank=True)
    slack_timestamp = models.CharField(max_length=100,blank=True)


class MatchQueue(models.Model):
    proposal = models.OneToOneField(IssueProposal,on_delete=models.PROTECT,related_name='matching_work')
    status = models.CharField(max_length=20,default='waiting')
    catalog_generation = models.PositiveBigIntegerField(default=0)
    calibration_id_snapshot = models.PositiveBigIntegerField(default=0)
    embedding_model = models.CharField(max_length=100,blank=True)
    last_processed_at = models.DateTimeField(null=True)
