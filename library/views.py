from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from .models import Baseline, Control, Profile, Modifier
from . import services

class BaselineForm(forms.Form):
    version = forms.SlugField(max_length=80)
    coverage_gaps = forms.CharField(widget=forms.Textarea, help_text='Record missing coverage, unverified mappings, and review limitations.')
class ApprovalForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea, label='Review and approval rationale')
    confirmed = forms.BooleanField(label='I reviewed this snapshot and understand approval is not certification.')
    coverage_reviewed = forms.BooleanField(label='I reviewed coverage and recorded missing safeguards or limitations.')
    applicability_reviewed = forms.BooleanField(label='I reviewed profile/modifier applicability and exceptions.')
    sources_reviewed = forms.BooleanField(label='I reviewed source references and unverified mappings.')

@staff_member_required
def dashboard(request):
    controls = Control.objects.prefetch_related('actions')
    profile = request.GET.get('profile','')
    if profile:
        controls = controls.filter(profiles__pk=profile) | controls.filter(universal=True) if profile.isdigit() else controls.none()
    return render(request,'library/dashboard.html',{'controls':controls.distinct(),'profiles':Profile.objects.all(),'baselines':Baseline.objects.all(),'form':BaselineForm(),'selected_profile':profile,'modifiers':Modifier.objects.all()})

@staff_member_required
@require_POST
def create_baseline(request):
    form = BaselineForm(request.POST)
    if form.is_valid():
        try:
            baseline = services.create_baseline(user=request.user,**form.cleaned_data)
            return redirect('baseline_detail',pk=baseline.pk)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, 'Version already exists.' if isinstance(exc,IntegrityError) else exc)
    return render(request,'library/form.html',{'form':form,'title':'Create baseline snapshot'},status=400)

@staff_member_required
def baseline_detail(request,pk):
    return render(request,'library/baseline.html',{'baseline':get_object_or_404(Baseline,pk=pk),'form':ApprovalForm()})

@staff_member_required
@require_POST
def approve_baseline(request,pk):
    get_object_or_404(Baseline,pk=pk)
    form = ApprovalForm(request.POST)
    if form.is_valid():
        try:
            services.approve_baseline(pk=pk,user=request.user,note=form.cleaned_data['note'] + '\nReview confirmed: coverage/limitations, applicability/exceptions, sources/mappings; approval is not certification.')
            return redirect('baseline_detail',pk=pk)
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,'library/form.html',{'form':form,'title':'Approve baseline'},status=400)


class RevisionForm(BaselineForm):
    revision_note = forms.CharField(widget=forms.Textarea, label='Reason for replacing this draft')


class SupersedeForm(forms.Form):
    replacement = forms.ModelChoiceField(queryset=Baseline.objects.none())
    note = forms.CharField(widget=forms.Textarea, label='Reason for superseding')

    def __init__(self, *args, source, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['replacement'].queryset = Baseline.objects.filter(created_at__gt=source.created_at, superseded_by__isnull=True, replaces__isnull=True)


@staff_member_required
@require_http_methods(["GET", "POST"])
def revise_baseline(request, pk):
    source = get_object_or_404(Baseline, pk=pk)
    if source.approved_at or source.superseded_by_id:
        return render(request, 'library/revise.html', {'source':source}, status=409)
    form = RevisionForm(request.POST if request.method == 'POST' else None, initial={'coverage_gaps':source.coverage_gaps})
    if request.method == 'POST' and form.is_valid():
        try:
            replacement = services.revise_draft(pk=pk, user=request.user, **form.cleaned_data)
            return redirect('baseline_detail', pk=replacement.pk)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, 'Version already exists.' if isinstance(exc, IntegrityError) else exc)
    return render(request, 'library/revise.html', {'source':source, 'form':form, 'supersede_form':SupersedeForm(source=source)}, status=400 if request.method == 'POST' else 200)


@staff_member_required
@require_POST
def supersede_baseline(request, pk):
    source = get_object_or_404(Baseline, pk=pk)
    form = SupersedeForm(request.POST, source=source)
    if form.is_valid():
        try:
            replacement = services.supersede_draft(pk=pk, replacement_pk=form.cleaned_data['replacement'].pk, user=request.user, note=form.cleaned_data['note'])
            return redirect('baseline_detail', pk=replacement.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'library/form.html', {'form':form,'title':'Supersede draft'}, status=400)
