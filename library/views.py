from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .models import Baseline, Control, Profile, Modifier
from . import services

class BaselineForm(forms.Form):
    version = forms.SlugField(max_length=80)
    coverage_gaps = forms.CharField(widget=forms.Textarea, help_text='Record missing coverage, unverified mappings, and review limitations.')
class ApprovalForm(forms.Form):
    note = forms.CharField(widget=forms.Textarea, label='Review and approval rationale')
    confirmed = forms.BooleanField(label='I reviewed this snapshot, applicability, sources, and coverage gaps.')

@staff_member_required
def dashboard(request):
    controls = Control.objects.all()
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
            services.approve_baseline(pk=pk,user=request.user,note=form.cleaned_data['note'])
            return redirect('baseline_detail',pk=pk)
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,'library/form.html',{'form':form,'title':'Approve baseline'},status=400)
