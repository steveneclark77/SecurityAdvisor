from pathlib import Path
from django import forms
from django.core.exceptions import ValidationError
from library.models import Baseline
from library.management.commands.seed_library import PROFILES, MODIFIERS
from .models import Customer, Engagement, ActionResult, EvidenceRequest, Evidence, Finding, Remediation, Retest, Reassessment, Contact, EngagementContact


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3
            if isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs={'type':'date'})


class CustomerForm(StyledModelForm):
    synthetic_confirmed = forms.BooleanField(label='This is a synthetic customer containing no real customer information.')
    class Meta:
        model = Customer
        fields = ['name']


class EngagementForm(StyledModelForm):
    class Meta:
        model = Engagement
        exclude = ['customer','created_at','legacy_contact_note']


class AssessmentForm(forms.Form):
    baseline = forms.ModelChoiceField(queryset=Baseline.objects.filter(approved_at__isnull=False, superseded_by__isnull=True))
    profile = forms.ChoiceField(choices=[])
    modifiers = forms.MultipleChoiceField(choices=[],required=False,widget=forms.CheckboxSelectMultiple)
    rationale = forms.CharField(widget=forms.Textarea, help_text='Explain applicability, confirm intake recommendations, and justify overrides.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        baseline = None
        candidate = self.data.get('baseline') if self.is_bound else self.initial.get('baseline')
        if isinstance(candidate, Baseline):
            baseline = candidate
        elif candidate and str(candidate).isdigit():
            baseline = self.fields['baseline'].queryset.filter(pk=candidate).first()
        # Union is only for display; the service validates against the selected snapshot.
        snapshots = [baseline.snapshot] if baseline else [b.snapshot for b in self.fields['baseline'].queryset]
        for name in ['profile','modifiers']:
            key = 'profiles' if name == 'profile' else 'modifiers'
            choices = sorted({item for snapshot in snapshots for item in snapshot.get(key,[])})
            self.fields[name].choices = [(item,item) for item in choices]


class ScopedForm(StyledModelForm):
    def __init__(self, *args, engagement, **kwargs):
        self.engagement = engagement
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not hasattr(field, 'queryset'):
                continue
            if name in ['evidence','request']:
                field.queryset = field.queryset.filter(engagement=engagement)
            elif name == 'inventory_items':
                field.queryset = field.queryset.filter(customer=engagement.customer)
                candidate = self.data.get('assessment') if self.is_bound else getattr(self.instance,'assessment_id',None)
                selected = engagement.assessments.filter(pk=candidate).first() if candidate and str(candidate).isdigit() else None
                allowed = [item['id'] for item in (selected.inventory_snapshot or {}).get('items',[])] if selected else []
                field.queryset = field.queryset.filter(pk__in=allowed)
            elif name == 'actions':
                field.queryset = field.queryset.filter(assessment__engagement=engagement)
                assessment_id = self.data.get('assessment') if self.is_bound else getattr(self.instance,'assessment_id',None)
                if assessment_id and str(assessment_id).isdigit():
                    field.queryset = field.queryset.filter(assessment_id=assessment_id)
            elif name == 'assessment':
                field.queryset = field.queryset.filter(engagement=engagement)
            elif name == 'dependencies':
                field.queryset = field.queryset.filter(finding__engagement=engagement).exclude(pk=self.instance.pk)


class ActionResultForm(ScopedForm):
    class Meta:
        model = ActionResult
        fields = ['applicability','applicability_reason','implementation','verification','confidence','observation','investigation_owner','followup_due','evidence','evidence_date']

    def clean(self):
        data = super().clean()
        if data.get('applicability') == 'excluded' and data.get('verification') != 'not_tested':
            raise ValidationError('Excluded actions cannot be marked as tested. Change applicability or clear the verification result.')
        if data.get('verification') in ['passed','failed','inconclusive']:
            if not data.get('observation') or not data.get('evidence_date') or not data.get('evidence'):
                raise ValidationError('Verification requires observations, an evidence date, and linked evidence.')
        return data


class EvidenceRequestForm(StyledModelForm):
    class Meta:
        model = EvidenceRequest
        exclude = ['engagement','assessment','control_code']


def validate_evidence_file(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Files must be 5 MB or smaller.')
    suffix = Path(upload.name).suffix.lower()
    head = upload.read(1024)
    upload.seek(0)
    valid = (suffix == '.pdf' and head.startswith(b'%PDF-')) or (suffix == '.png' and head.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix in ['.jpg','.jpeg'] and head.startswith(b'\xff\xd8\xff'))
    if suffix == '.txt':
        try:
            upload.read().decode('utf-8')
            valid = b'\x00' not in head
        except UnicodeDecodeError:
            valid = False
        finally:
            upload.seek(0)
    if not valid:
        raise ValidationError('Upload a UTF-8 text, PDF, PNG, or JPEG file with matching contents. Synthetic/redacted evidence only.')
    return upload


class EvidenceForm(ScopedForm):
    class Meta:
        model = Evidence
        exclude = ['engagement','created_at']

    def clean_file(self):
        upload = self.cleaned_data.get('file')
        return validate_evidence_file(upload) if upload and hasattr(upload,'content_type') else upload


class FindingForm(ScopedForm):
    class Meta:
        model = Finding
        exclude = ['engagement']


class RemediationForm(ScopedForm):
    class Meta:
        model = Remediation
        exclude = ['finding']

    def clean_dependencies(self):
        dependencies = self.cleaned_data['dependencies']
        if self.instance.pk:
            seen = set()
            stack = list(dependencies)
            while stack:
                dependency = stack.pop()
                if dependency.pk == self.instance.pk:
                    raise ValidationError('Dependencies cannot form a cycle.')
                if dependency.pk not in seen:
                    seen.add(dependency.pk)
                    stack.extend(dependency.dependencies.all())
        return dependencies

    def clean(self):
        data = super().clean()
        if data.get('status') in ['in_progress','implemented','partial','verified']:
            if any(task.status != 'verified' for task in data.get('dependencies', [])):
                raise ValidationError('Verify dependencies before implementing this task, or revise the plan.')
        if data.get('status') == 'verified' and not data.get('verified_residual_risk'):
            raise ValidationError('Record verified residual risk before marking the task verified.')
        return data


class RetestForm(ScopedForm):
    class Meta:
        model = Retest
        exclude = ['task','tester','created_at']

    def clean_evidence(self):
        evidence = self.cleaned_data['evidence']
        if not evidence:
            raise ValidationError('Link evidence of the retest.')
        return evidence


class ReassessmentForm(StyledModelForm):
    class Meta:
        model = Reassessment
        fields = ['status','decision','review_date']

    def clean(self):
        data = super().clean()
        if data.get('status') != 'pending' and not data.get('decision','').strip():
            raise ValidationError('Explain your reassessment decision.')
        if data.get('status') == 'planned' and not data.get('review_date'):
            raise ValidationError('Schedule the planned reassessment.')
        return data


class IntakeForm(forms.Form):
    industry = forms.ChoiceField(choices=[('',"I don't know / mixed business")]+[(p,p) for p in PROFILES], required=False)
    activities = forms.CharField(widget=forms.Textarea, required=False, help_text="Describe the business; 'unknown' is acceptable.")
    modifiers = forms.MultipleChoiceField(choices=[(m,m) for m in MODIFIERS], required=False, widget=forms.CheckboxSelectMultiple)
    technologies = forms.CharField(widget=forms.Textarea, required=False, help_text='Include payroll/benefits providers, accounting/file sharing, computers and security configuration, ISP/network services, physical security, and public sites. Names may be unknown at intake.')
    critical_operations = forms.CharField(widget=forms.Textarea, required=False, help_text='Include customer service, payroll, vendor/rent payments, and IT maintenance, with deadlines or critical periods.')
    outage_tolerance = forms.CharField(widget=forms.Textarea, required=False)
    financial_context = forms.CharField(widget=forms.Textarea, required=False)
    sensitive_data = forms.CharField(widget=forms.Textarea, required=False)
    unknowns = forms.CharField(label='Information to confirm',widget=forms.Textarea, required=False, help_text='Missing environment facts: provider names, software/features, laptop configurations, ISP/bundled security, physical systems, administrators, and connections. Safeguard effectiveness is assessed separately.')


class EvidenceResponseForm(forms.Form):
    title = forms.CharField(max_length=200)
    notes = forms.CharField(widget=forms.Textarea)
    provenance = forms.CharField(max_length=200)
    collected_on = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    file = forms.FileField(required=False, validators=[validate_evidence_file])


class ContactForm(StyledModelForm):
    class Meta:
        model = Contact
        exclude = ['managers','created_at']

    def __init__(self, *args, shared=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop('archived', None)
        if shared:
            self.fields['confirm_shared_edit'] = forms.BooleanField(label='I understand that these shared contact details change everywhere this person is linked.')


CONTACT_ROLES = [('business_owner','Business owner'),('technical','Technical contact'),('evidence','Evidence provider'),('remediation','Remediation implementer'),('other','Other stakeholder')]


class EngagementContactForm(StyledModelForm):
    roles = forms.MultipleChoiceField(choices=CONTACT_ROLES, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = EngagementContact
        exclude = ['engagement','contact']
