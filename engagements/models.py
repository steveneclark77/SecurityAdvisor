import uuid
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


def evidence_path(instance, filename):
    return f'{instance.engagement_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class Customer(models.Model):
    name = models.CharField(max_length=180)
    assigned_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_customers')
    synthetic = models.BooleanField(default=True, help_text='Only synthetic customers are supported in this development milestone.')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Engagement(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='engagements')
    title = models.CharField(max_length=180)
    scope = models.TextField()
    exclusions = models.TextField(blank=True)
    contact = models.CharField(max_length=200)
    assessment_authorization = models.TextField(help_text='Who authorized which assessment methods, when, and with what restrictions?')
    change_authorization = models.TextField(blank=True, help_text='Separate authorization for implementation; leave blank until obtained.')
    deliverables = models.TextField()
    target_date = models.DateField(null=True, blank=True)
    next_review = models.DateField(null=True, blank=True)
    review_triggers = models.TextField(blank=True)
    financial_thresholds = models.TextField(help_text='Describe customer-specific financial impact levels 1–5; unknowns may be recorded explicitly.')
    outage_tolerance = models.TextField()
    critical_operations = models.TextField()
    reputation_context = models.TextField()
    data_handling = models.TextField(default='Synthetic data only. Three-year retention required; clock start and exceptions not yet agreed.')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.customer}: {self.title}'


class Intake(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='intakes')
    answers = models.JSONField()
    recommendation = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)


class Assessment(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.PROTECT, related_name='assessments')
    baseline = models.ForeignKey('library.Baseline', on_delete=models.PROTECT)
    profile = models.CharField(max_length=180)
    modifiers = models.JSONField(default=list)
    applicability_rationale = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


APPLICABILITY = [('applicable', 'Applicable'), ('unknown', 'Unknown — investigate'), ('excluded', 'Excluded — reason required')]
IMPLEMENTATION = [('unknown', 'Unknown'), ('absent', 'Not implemented'), ('partial', 'Partially implemented'), ('implemented', 'Implemented')]
VERIFICATION = [('not_tested', 'Not tested'), ('passed', 'Passed'), ('failed', 'Failed'), ('inconclusive', 'Inconclusive')]
CONFIDENCE = [('unknown', 'Unknown'), ('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]


class ActionResult(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='results')
    control_code = models.CharField(max_length=80)
    control_title = models.CharField(max_length=200)
    guidance = models.JSONField(help_text='Frozen control and action guidance from the selected baseline.')
    applicability = models.CharField(max_length=20, choices=APPLICABILITY, default='unknown')
    applicability_reason = models.TextField()
    implementation = models.CharField(max_length=20, choices=IMPLEMENTATION, default='unknown')
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='not_tested')
    confidence = models.CharField(max_length=20, choices=CONFIDENCE, default='unknown')
    observation = models.TextField(blank=True)
    investigation_owner = models.CharField(max_length=180, blank=True)
    followup_due = models.DateField(null=True, blank=True)
    evidence = models.ManyToManyField('Evidence', blank=True, related_name='action_results')
    evidence_date = models.DateField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['control_code', 'pk']

    def __str__(self):
        return f'{self.control_code} · {self.guidance["action"]["instruction"][:90]}'


class EvidenceRequest(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, null=True, blank=True)
    control_code = models.CharField(max_length=80, blank=True)
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='evidence_requests')
    title = models.CharField(max_length=200)
    instructions = models.TextField(help_text='Request redacted evidence, with examples; never request credentials.')
    owner = models.CharField(max_length=180)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('requested','Requested'),('received','Received'),('reviewed','Reviewed')], default='requested')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['assessment','control_code'], condition=models.Q(assessment__isnull=False), name='unique_assessment_control_request')]

    def __str__(self):
        return self.title


class Evidence(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, related_name='evidence')
    request = models.ForeignKey(EvidenceRequest, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    notes = models.TextField()
    provenance = models.CharField(max_length=200, help_text='Source, author, and date; distinguish customer statements from tested evidence.')
    collected_on = models.DateField()
    file = models.FileField(upload_to=evidence_path, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


PRIORITY = [('unrated','Unrated'),('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')]
rating_validators = [MinValueValidator(1), MaxValueValidator(5)]


class Finding(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.PROTECT, related_name='findings')
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='findings')
    title = models.CharField(max_length=200)
    condition = models.TextField()
    affected_assets = models.TextField()
    business_consequence = models.TextField()
    technical_detail = models.TextField()
    actions = models.ManyToManyField(ActionResult, blank=True, related_name='findings')
    evidence = models.ManyToManyField(Evidence, blank=True, related_name='findings')
    financial_impact = models.TextField()
    availability_impact = models.TextField()
    reputation_impact = models.TextField()
    other_impact = models.TextField(blank=True)
    impact = models.PositiveSmallIntegerField(null=True, blank=True, validators=rating_validators)
    likelihood = models.PositiveSmallIntegerField(null=True, blank=True, validators=rating_validators)
    likelihood_rationale = models.TextField()
    confidence = models.CharField(max_length=20, choices=CONFIDENCE, default='unknown')
    priority = models.CharField(max_length=20, choices=PRIORITY, default='unrated')
    priority_rationale = models.TextField(help_text='Consultant judgment; the automatic priority matrix is not yet approved.')
    recommendation = models.TextField()
    expected_residual_risk = models.TextField()
    limitations = models.TextField()
    risk_acceptance = models.TextField(blank=True, help_text='Decision-maker, rationale, and accepted residual risk.')
    acceptance_review = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.assessment_id and self.engagement_id and self.assessment.engagement_id != self.engagement_id:
            raise ValidationError('Finding and assessment must belong to the same engagement.')
        if self.priority != 'unrated' and (self.impact is None or self.likelihood is None):
            raise ValidationError('A priority requires both impact and likelihood; leave unknown risks unrated.')
        if self.risk_acceptance.strip() and not self.acceptance_review:
            raise ValidationError('Risk acceptance requires a review date.')


class Remediation(models.Model):
    finding = models.ForeignKey(Finding, on_delete=models.PROTECT, related_name='tasks')
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    owner = models.CharField(max_length=180)
    due_date = models.DateField(null=True, blank=True)
    estimated_cost = models.CharField(max_length=200)
    estimated_effort = models.CharField(max_length=200)
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True)
    temporary_safeguards = models.TextField(blank=True)
    authorization = models.TextField(blank=True, help_text='Customer authorization specific to this change.')
    recovery_plan = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[('planned','Planned'),('in_progress','In progress'),('implemented','Implemented — verification pending'),('partial','Partially remediated'),('verified','Verified'),('reopened','Reopened')], default='planned')
    implementation_notes = models.TextField(blank=True)
    verification_plan = models.TextField()
    verified_residual_risk = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.status in ['in_progress','implemented','partial','verified'] and not self.authorization.strip():
            raise ValidationError('Implementation requires separate change authorization.')
        if self.pk and self.status == 'verified' and (not self.retests.exists() or self.retests.latest('created_at').outcome != 'passed'):
            raise ValidationError('Record a passing retest before marking the task verified.')
        if not self.pk and self.status == 'verified':
            raise ValidationError('Create the task and record a passing retest first.')


class Retest(models.Model):
    task = models.ForeignKey(Remediation, on_delete=models.PROTECT, related_name='retests')
    tester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    tested_on = models.DateField()
    outcome = models.CharField(max_length=20, choices=[('passed','Passed'),('failed','Failed'),('partial','Partial'),('inconclusive','Inconclusive')])
    procedure_and_result = models.TextField()
    evidence = models.ManyToManyField(Evidence, blank=True)
    residual_risk = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Invite(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=20, choices=[('intake','Intake'),('evidence','Evidence response')])
    request = models.ForeignKey(EvidenceRequest, on_delete=models.CASCADE, null=True, blank=True)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    draft_answers = models.JSONField(default=dict)


class AuditEvent(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=250)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Engagement history is append-only.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Engagement history must be preserved.')


class Report(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.PROTECT, related_name='reports')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Reports are preserved snapshots. Generate a new report for changes.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Report history must be preserved.')


class Reassessment(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='reassessments')
    baseline = models.ForeignKey('library.Baseline', on_delete=models.PROTECT)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=[('pending','Pending review'),('planned','Reassessment planned'),('dismissed','Dismissed with rationale')], default='pending')
    decision = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['assessment','baseline'], name='unique_assessment_baseline_review')]
