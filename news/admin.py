from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.http import Http404, HttpResponseRedirect
from django.utils.html import format_html
from .models import Issue, IssueVersion, IssueVersionReference, Review, Scan, Source
from .versioning import CONTENT_FIELDS, create_version, reference_data


class RetainedAdmin(admin.ModelAdmin):
    class Media:
        js = ['library/forms.js']

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Source)
class SourceAdmin(RetainedAdmin):
    list_display = ['name', 'enabled', 'feed_url']
    list_filter = ['enabled']
    search_fields = ['name', 'notes']


@admin.register(Issue)
class IssueAdmin(RetainedAdmin):
    list_display = ['name', 'source', 'current_version', 'discovered_at', 'review_status']
    list_filter = ['source', 'current_version__severity', 'current_version__kind']
    search_fields = ['current_version__name', 'current_version__description', 'current_version__identifiers']
    readonly_fields = ['source', 'first_scan', 'identity', 'discovered_at', 'last_seen_at', 'current_version', 'next_version', 'version_history']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def next_version(self, obj):
        return format_html('<a class="button" href="{}?issue={}&base_version={}">Create next version</a>', reverse('admin:news_issueversion_add'), obj.pk, obj.current_version_id or '')

    def version_history(self, obj):
        from django.utils.html import format_html_join
        return format_html_join(' · ', '<a href="{}">v{}</a>', [(reverse('admin:news_issueversion_change', args=[v.pk]), v.version_number) for v in obj.versions.all()])


class VersionForm(forms.ModelForm):
    base_version = forms.IntegerField(widget=forms.HiddenInput)
    inherit_references = forms.BooleanField(required=False, initial=True, label='Keep supporting references from the previous version')

    class Meta:
        model = IssueVersion
        fields = ['issue', *CONTENT_FIELDS, 'change_reason']
        widgets = {'issue': forms.HiddenInput()}

    def clean(self):
        data = super().clean()
        issue = data.get('issue')
        if issue:
            locked = Issue.objects.select_for_update().get(pk=issue.pk)
            if locked.current_version_id != data.get('base_version'):
                raise ValidationError('This issue changed while you were editing. Reload the latest version before saving.')
        return data


class ReferenceInline(admin.TabularInline):
    model = IssueVersionReference
    fields = ['source', 'source_url', 'source_published_at', 'notes']
    extra = 1


@admin.register(IssueVersion)
class VersionAdmin(RetainedAdmin):
    form = VersionForm
    inlines = [ReferenceInline]
    list_display = ['name', 'issue', 'version_number', 'severity', 'origin', 'created_by', 'created_at']
    list_filter = ['severity', 'origin']
    search_fields = ['name', 'identifiers']

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return super().has_add_permission(request) and request.user.has_perm('news.change_issue') and bool(request.GET.get('issue') or request.POST.get('issue'))

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in IssueVersion._meta.fields] + ['supporting_references'] if obj else ['version_number', 'origin', 'created_by', 'created_at']

    def get_fields(self, request, obj=None):
        if obj:
            return [field.name for field in IssueVersion._meta.fields] + ['supporting_references']
        return ['issue', 'base_version', *CONTENT_FIELDS, 'change_reason', 'inherit_references']

    def supporting_references(self, obj):
        from django.utils.html import format_html_join
        return format_html_join(' · ', '<a href="{}" rel="noreferrer">{} — {}</a>', [(ref.source_url, ref.source_name, ref.notes) for ref in obj.references.all()])

    def get_inlines(self, request, obj=None):
        return [] if obj else [ReferenceInline]

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        try:
            issue_id = int(request.GET.get('issue', ''))
        except (TypeError, ValueError) as exc:
            raise Http404('Select an existing issue.') from exc
        issue = Issue.objects.filter(pk=issue_id).select_related('current_version').first()
        if not issue or not issue.current_version_id:
            raise Http404('Select an existing versioned issue.')
        if issue and issue.current_version:
            initial.update({field: getattr(issue.current_version, field) for field in CONTENT_FIELDS})
            initial.update(issue=issue.pk, base_version=request.GET.get('base_version', issue.current_version_id))
        return initial

    def save_model(self, request, obj, form, change):
        # Save content and all supporting references atomically in save_related.
        pass

    def save_related(self, request, form, formsets, change):
        issue = form.cleaned_data['issue']
        references = reference_data(issue.current_version) if form.cleaned_data['inherit_references'] else []
        for formset in formsets:
            for row in formset.cleaned_data:
                if not row or row.get('DELETE') or not row.get('source'):
                    continue
                ref = {'source_id': row['source'].pk, 'source_url': row['source_url'], 'source_published_at': row.get('source_published_at'), 'notes': row.get('notes', '')}
                references = [r for r in references if r['source_url'] != ref['source_url']]
                references.append(ref)
            formset.new_objects, formset.changed_objects, formset.deleted_objects = [], [], []
        version = create_version(issue=issue, expected_version_id=form.cleaned_data['base_version'],
            content={field: form.cleaned_data[field] for field in CONTENT_FIELDS}, actor=request.user,
            change_reason=form.cleaned_data['change_reason'], references=references)
        form.instance.__dict__.update(version.__dict__)
        form.instance._unchanged = version.pk == form.cleaned_data['base_version']

    def log_addition(self, request, obj, message):
        if not getattr(obj, '_unchanged', False):
            return super().log_addition(request, obj, message)

    def response_add(self, request, obj, post_url_continue=None):
        if getattr(obj, '_unchanged', False):
            self.message_user(request, 'Content and references are unchanged; no new version was created.')
            return HttpResponseRedirect(reverse('admin:news_issueversion_change', args=[obj.pk]))
        return super().response_add(request, obj, post_url_continue)


@admin.register(IssueVersionReference)
class ReferenceAdmin(RetainedAdmin):
    list_display = ['version', 'source_name', 'source_url', 'source_published_at']
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Scan)
class ScanAdmin(RetainedAdmin):
    list_display = ['source', 'started_at', 'status', 'created_count', 'error']
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['issue_version'].required = True

    def clean(self):
        data = super().clean()
        if data.get('issue'):
            data['issue'] = Issue.objects.select_for_update().get(pk=data['issue'].pk)
        return data


@admin.register(Review)
class ReviewAdmin(RetainedAdmin):
    form = ReviewForm
    class Media:
        js = ['library/forms.js', 'news/review.js']

    list_display = ['issue', 'issue_version', 'decision', 'actor', 'created_at']
    exclude = ['actor']
    readonly_fields = ['created_at', 'issue_snapshot']
    filter_horizontal = ['controls']

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            issue = Issue.objects.select_for_update().get(pk=obj.issue_id)
            if obj.issue_version_id != issue.current_version_id:
                raise ValidationError('The issue changed; reload before reviewing.')
            obj.actor = request.user
            obj.issue_snapshot = {field: getattr(obj.issue_version, field) for field in CONTENT_FIELDS if field != 'published_at'}
            obj.issue_snapshot['published_at'] = obj.issue_version.published_at.isoformat() if obj.issue_version.published_at else None
            obj.issue_snapshot.update(version_number=obj.issue_version.version_number, references=[{**r, 'source_published_at': str(r['source_published_at']) if r['source_published_at'] else None} for r in reference_data(obj.issue_version)])
            super().save_model(request, obj, form, change)
