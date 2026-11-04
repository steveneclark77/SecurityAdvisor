from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models

class Profile(models.Model):
    name = models.CharField(max_length=160, unique=True)
    class Meta:
        ordering = ['name']
    def __str__(self): return self.name

class Modifier(models.Model):
    name = models.CharField(max_length=160, unique=True)
    def __str__(self): return self.name

class Control(models.Model):
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    function = models.CharField(max_length=20, choices=[(x,x) for x in ['Govern','Identify','Protect','Detect','Respond','Recover']])
    universal = models.BooleanField(default=True)
    profiles = models.ManyToManyField(Profile, blank=True)
    modifiers = models.ManyToManyField(Modifier, blank=True)
    applicability = models.TextField()
    investigation = models.TextField()
    evidence = models.TextField()
    risk = models.TextField()
    recommendation = models.TextField()
    verification = models.TextField()
    estimated_cost = models.CharField(max_length=200, default='Estimate per customer after investigation')
    estimated_effort = models.CharField(max_length=200, default='Estimate per customer after investigation')
    references = models.TextField(help_text='One source URL or reference per line; mappings are not certification.')
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['code']
    def __str__(self): return f'{self.code}: {self.title}'
    def snapshot(self):
        names = ['code','title','function','universal','applicability','investigation','evidence','risk','recommendation','verification','estimated_cost','estimated_effort','references']
        return {**{name:getattr(self,name) for name in names},'profiles':list(self.profiles.order_by('name').values_list('name',flat=True)),'modifiers':list(self.modifiers.order_by('name').values_list('name',flat=True))}

class Baseline(models.Model):
    version = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_baselines')
    snapshot = models.JSONField()
    coverage_gaps = models.TextField()
    approval_note = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='approved_baselines')
    class Meta:
        ordering = ['-created_at']
    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            preserved = ['version','created_by_id','snapshot','coverage_gaps']
            if any(getattr(previous, field) != getattr(self, field) for field in preserved):
                raise ValidationError('Captured baseline content cannot be edited; create a new version.')
            if previous.approved_at:
                raise ValidationError('An approved baseline cannot be changed.')
        super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('Baseline history must be preserved.')
    def __str__(self): return self.version
