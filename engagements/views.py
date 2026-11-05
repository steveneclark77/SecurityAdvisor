import hashlib
from pathlib import Path
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from . import forms, services
from .models import Customer, Engagement, Assessment, ActionResult, EvidenceRequest, Evidence, Finding, Remediation, Retest, Invite, Intake, Report, Reassessment, Contact, EngagementContact


def consultant(view):
    return never_cache(staff_member_required(view))


def engagements_for(user):
    return Engagement.objects.filter(customer__assigned_users=user).distinct()


def engagement_for(user, pk):
    return get_object_or_404(engagements_for(user).select_related('customer'), pk=pk)


@consultant
def index(request):
    return render(request, 'engagements/index.html', {'customers':Customer.objects.filter(assigned_users=request.user), 'engagements':engagements_for(request.user), 'reviews':Reassessment.objects.filter(assessment__engagement__in=engagements_for(request.user)).select_related('assessment__engagement','baseline')})


@consultant
@require_http_methods(['GET','POST'])
def customer_new(request):
    form = forms.CustomerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            customer = form.save()
            customer.assigned_users.add(request.user)
        return redirect('engagement_new', customer_pk=customer.pk)
    return render(request, 'engagements/form.html', {'form':form,'title':'Create a synthetic customer'})


@consultant
@require_http_methods(['GET','POST'])
def engagement_new(request, customer_pk):
    customer = get_object_or_404(Customer.objects.filter(assigned_users=request.user), pk=customer_pk)
    obj = Engagement(customer=customer)
    return edit(request, forms.EngagementForm, obj, obj, 'Create engagement', next_route='engagement_contacts')


@consultant
def detail(request, pk):
    engagement = engagement_for(request.user, pk)
    return render(request, 'engagements/detail.html', {'engagement':engagement, 'intake':engagement.intakes.order_by('-submitted_at').first()})


@consultant
@require_http_methods(['GET','POST'])
def engagement_edit(request, pk):
    engagement = engagement_for(request.user, pk)
    return edit(request, forms.EngagementForm, engagement, engagement, 'Edit scope and business context')


def record_state(obj):
    if not obj.pk:
        return {}
    state = {}
    for field in obj._meta.fields:
        value = getattr(obj, field.attname)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif hasattr(value, 'name'):
            value = value.name
        state[field.name] = value
    for field in obj._meta.many_to_many:
        state[field.name] = list(getattr(obj, field.name).values_list('pk',flat=True))
    return state


def edit(request, form_class, obj, engagement, title, *, scoped=False, after_save=None, initial=None, next_route="engagement_detail"):
    before = record_state(obj)
    kwargs = {'instance':obj, 'initial':initial or {}}
    if scoped:
        kwargs['engagement'] = engagement
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, **kwargs)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save(commit=False)
                if after_save:
                    after_save(saved)
                saved.save()
                form.save_m2m()
                services.audit(engagement, request.user, f'{title}: record {saved.pk}.', {'before':before, 'after':record_state(saved)})
            return redirect(next_route, pk=engagement.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'engagements/form.html', {'form':form,'title':title,'engagement':engagement,'obj':obj}, status=400 if request.method == 'POST' else 200)


@consultant
@require_http_methods(['GET','POST'])
def assessment_new(request, pk):
    engagement = engagement_for(request.user, pk)
    intake = engagement.intakes.order_by('-submitted_at').first()
    initial = {'profile':intake.recommendation['profile'],'modifiers':intake.recommendation['modifiers']} if intake else {}
    form = forms.AssessmentForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            assessment = services.start_assessment(engagement=engagement, user=request.user, **form.cleaned_data)
            return redirect('assessment_detail', pk=assessment.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'engagements/form.html', {'form':form,'title':'Confirm applicability and start assessment','engagement':engagement})


@consultant
def assessment_detail(request, pk):
    assessment = get_object_or_404(Assessment.objects.filter(engagement__in=engagements_for(request.user)).select_related('engagement','baseline'), pk=pk)
    results = assessment.results.all()
    applicability = request.GET.get('applicability','')
    if applicability in ['applicable','unknown','excluded']:
        results = results.filter(applicability=applicability)
    return render(request, 'engagements/assessment.html', {'assessment':assessment,'results':results,'engagement':assessment.engagement})


@consultant
@require_http_methods(['GET','POST'])
def action_edit(request, pk):
    obj = get_object_or_404(ActionResult.objects.filter(assessment__engagement__in=engagements_for(request.user)).select_related('assessment__engagement'), pk=pk)
    def verified(saved):
        if saved.verification != 'not_tested':
            saved.verified_by = request.user
            saved.verified_at = timezone.now()
        else:
            saved.verified_by = None
            saved.verified_at = None
    return edit(request, forms.ActionResultForm, obj, obj.assessment.engagement, 'Record action investigation', scoped=True, after_save=verified)


@consultant
@require_http_methods(['GET','POST'])
def request_new(request, pk):
    engagement = engagement_for(request.user, pk)
    return edit(request, forms.EvidenceRequestForm, EvidenceRequest(engagement=engagement), engagement, 'Create evidence request')


@consultant
@require_http_methods(['GET','POST'])
def request_edit(request, pk):
    obj = get_object_or_404(EvidenceRequest.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    return edit(request, forms.EvidenceRequestForm, obj, obj.engagement, 'Review evidence request')


@consultant
@require_http_methods(['GET','POST'])
def evidence_new(request, pk):
    engagement = engagement_for(request.user, pk)
    return edit(request, forms.EvidenceForm, Evidence(engagement=engagement), engagement, 'Record evidence', scoped=True)


@consultant
def evidence_download(request, pk):
    evidence = get_object_or_404(Evidence.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    if not evidence.file:
        raise Http404
    services.audit(evidence.engagement, request.user, f'Downloaded evidence {evidence.pk}.')
    return FileResponse(evidence.file.open('rb'), as_attachment=True, filename=f'evidence-{evidence.pk}{Path(evidence.file.name).suffix}', content_type='application/octet-stream')


@consultant
@require_http_methods(['GET','POST'])
def finding_new(request, pk):
    engagement = engagement_for(request.user, pk)
    obj = Finding(engagement=engagement)
    initial = {}
    if request.GET.get('action'):
        if not request.GET['action'].isdigit():
            raise Http404
        action = get_object_or_404(ActionResult.objects.filter(assessment__engagement=engagement), pk=request.GET['action'])
        obj.assessment = action.assessment
        obj.title = f'{action.control_code}: {action.control_title}'
        obj.condition = action.observation
        obj.technical_detail = action.guidance['action']['instruction']
        obj.business_consequence = action.guidance['control'].get('risk','')
        obj.recommendation = action.guidance['control'].get('recommendation','')
        initial = {'actions':[action.pk], 'evidence':list(action.evidence.values_list('pk',flat=True))}
    return edit(request, forms.FindingForm, obj, engagement, 'Create finding', scoped=True, initial=initial)


@consultant
@require_http_methods(['GET','POST'])
def finding_edit(request, pk):
    obj = get_object_or_404(Finding.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    return edit(request, forms.FindingForm, obj, obj.engagement, 'Edit finding', scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def task_new(request, pk):
    finding = get_object_or_404(Finding.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    obj = Remediation(finding=finding, instructions=finding.recommendation, owner="Unassigned", estimated_cost='Estimate pending', estimated_effort='Estimate pending', verification_plan='\n'.join(a.guidance['action'].get('verification','') for a in finding.actions.all()))
    return edit(request, forms.RemediationForm, obj, finding.engagement, 'Plan remediation', scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def task_edit(request, pk):
    obj = get_object_or_404(Remediation.objects.filter(finding__engagement__in=engagements_for(request.user)), pk=pk)
    return edit(request, forms.RemediationForm, obj, obj.finding.engagement, 'Update remediation', scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def retest_new(request, pk):
    task = get_object_or_404(Remediation.objects.filter(finding__engagement__in=engagements_for(request.user)), pk=pk)
    engagement = task.finding.engagement
    form = forms.RetestForm(request.POST if request.method == 'POST' else None, engagement=engagement, instance=Retest(task=task, tester=request.user))
    if request.method == 'POST' and form.is_valid():
        if not task.authorization.strip():
            form.add_error(None, 'Obtain change/retest authorization before recording remediation verification.')
        elif task.dependencies.exclude(status='verified').exists():
            form.add_error(None, 'Verify task dependencies before recording a remediation retest.')
        else:
            with transaction.atomic():
                # Serialize retests and task status changes for the same remediation.
                task = Remediation.objects.select_for_update().get(pk=task.pk)
                retest = form.save()
                task.status = {'passed':'verified','failed':'reopened','partial':'partial','inconclusive':'implemented'}[retest.outcome]
                task.verified_residual_risk = retest.residual_risk
                task.save()
                services.audit(engagement, request.user, f'Retested task {task.pk}: {retest.outcome}.')
            return redirect('engagement_detail', pk=engagement.pk)
    return render(request, 'engagements/form.html', {'form':form,'title':'Retest remediation','engagement':engagement}, status=400 if request.method == 'POST' else 200)


@consultant
@require_POST
def invite_new(request, pk):
    engagement = engagement_for(request.user, pk)
    evidence_request = None
    purpose = request.POST.get('purpose')
    if purpose == 'evidence':
        if not request.POST.get('request_id','').isdigit():
            raise Http404
        evidence_request = get_object_or_404(engagement.evidence_requests, pk=request.POST.get('request_id'))
    try:
        token = services.issue_invite(engagement=engagement, user=request.user, purpose=purpose, evidence_request=evidence_request)
    except ValidationError:
        return HttpResponse('Invalid invitation purpose.', status=400)
    return render(request, 'engagements/invite.html', {'engagement':engagement,'path':reverse('public_response',args=[token])})


@consultant
@require_POST
def revoke_invites(request, pk):
    engagement = engagement_for(request.user, pk)
    Invite.objects.filter(engagement=engagement, used_at__isnull=True).update(expires_at=timezone.now())
    services.audit(engagement, request.user, 'Revoked all unused engagement invitations.')
    return redirect('engagement_detail', pk=pk)


@never_cache
@require_http_methods(['GET','POST'])
def public_response(request, token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    # Same response for expired, invalid, revoked, and already-used tokens.
    invite = get_object_or_404(Invite.objects.select_related('request'), token_digest=digest, expires_at__gt=timezone.now(), used_at__isnull=True)
    form_class = forms.IntakeForm if invite.purpose == 'intake' else forms.EvidenceResponseForm
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, initial=invite.draft_answers)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            invite = get_object_or_404(Invite.objects.select_for_update(), pk=invite.pk, expires_at__gt=timezone.now(), used_at__isnull=True)
            if invite.purpose == 'intake' and request.POST.get('intent') == 'save':
                invite.draft_answers = form.cleaned_data
                invite.save(update_fields=['draft_answers'])
                return render(request, 'engagements/public.html', {'form':form,'invite':invite,'saved':True})
            if invite.purpose == 'intake':
                Intake.objects.create(engagement=invite.engagement, answers=form.cleaned_data, recommendation=services.recommend_profile(form.cleaned_data))
            else:
                Evidence.objects.create(engagement=invite.engagement, request=invite.request, **form.cleaned_data)
                invite.request.status = 'received'
                invite.request.save(update_fields=['status'])
            invite.used_at = timezone.now()
            invite.draft_answers = {}
            invite.save(update_fields=['used_at','draft_answers'])
            services.audit(invite.engagement, None, f'Received {invite.purpose} response via invitation {invite.pk}.')
        return render(request, 'engagements/thanks.html')
    return render(request, 'engagements/public.html', {'form':form,'invite':invite})


@consultant
@require_POST
def report_new(request, pk):
    engagement = engagement_for(request.user, pk)
    report = services.capture_report(engagement=engagement, user=request.user)
    return redirect('report_detail', pk=report.pk)


@consultant
def report_detail(request, pk):
    report = get_object_or_404(Report.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    return render(request, 'engagements/report.html', {'report':report,'data':report.snapshot,'engagement':report.engagement})


@consultant
@require_http_methods(['GET','POST'])
def reassessment_edit(request, pk):
    obj = get_object_or_404(Reassessment.objects.filter(assessment__engagement__in=engagements_for(request.user)), pk=pk)
    return edit(request, forms.ReassessmentForm, obj, obj.assessment.engagement, 'Review affected customer')


@consultant
@require_POST
def generate_requests(request, pk):
    assessment = get_object_or_404(Assessment.objects.filter(engagement__in=engagements_for(request.user)), pk=pk)
    with transaction.atomic():
        for result in assessment.results.exclude(applicability='excluded'):
            EvidenceRequest.objects.get_or_create(engagement=assessment.engagement, assessment=assessment, control_code=result.control_code, defaults={
                'title':f'{result.control_code}: {result.control_title}',
                'instructions':result.guidance['control'].get('evidence','Provide redacted evidence supporting this control.') + '\nSynthetic/redacted data only. Do not submit credentials.',
                'owner':'Unassigned',
            })
        services.audit(assessment.engagement, request.user, f'Generated evidence requests for assessment {assessment.pk}; existing requests preserved.')
    return redirect('engagement_detail', pk=assessment.engagement_id)


def contacts_for(user):
    from django.db.models import Q
    return Contact.objects.filter(Q(managers=user) | Q(engagement_links__engagement__customer__assigned_users=user)).distinct()


@consultant
def contact_index(request):
    return render(request, 'engagements/contacts.html', {'contacts':contacts_for(request.user), 'managed_ids':set(request.user.managed_contacts.values_list('pk',flat=True))})


@consultant
def engagement_contacts(request, pk):
    engagement = engagement_for(request.user, pk)
    linked = engagement.contact_links.values_list('contact_id',flat=True)
    available = request.user.managed_contacts.filter(archived=False).exclude(pk__in=linked)
    return render(request, 'engagements/contacts.html', {'engagement':engagement, 'links':engagement.contact_links.select_related('contact'), 'available':available, 'managed_ids':set(request.user.managed_contacts.values_list('pk',flat=True))})


@consultant
@require_http_methods(['GET','POST'])
def contact_new(request):
    engagement = None
    candidate = request.GET.get('engagement')
    if candidate:
        if not candidate.isdigit():
            raise Http404
        engagement = engagement_for(request.user, candidate)
    form = forms.ContactForm(request.POST if request.method == 'POST' else None)
    duplicates = False
    if request.method == 'POST' and form.is_valid():
        # Duplicate checks never search records the current user cannot access.
        from django.db.models import Q
        query = Q(first_name__iexact=form.cleaned_data['first_name'],last_name__iexact=form.cleaned_data['last_name'])
        if form.cleaned_data.get('email'):
            query |= Q(email__iexact=form.cleaned_data['email'])
        duplicates = contacts_for(request.user).filter(query).exists()
        if not duplicates or request.POST.get('confirm_duplicate') == 'on':
            with transaction.atomic():
                contact = form.save()
                contact.managers.add(request.user)
                if engagement:
                    services.audit(engagement, request.user, f'Created reusable contact {contact.pk}; engagement link pending.')
            if engagement:
                return redirect(reverse('contact_link',args=[engagement.pk,contact.pk]))
            return redirect('contact_index')
    return render(request, 'engagements/contact_form.html', {'form':form,'title':'Create contact','engagement':engagement,'duplicates':duplicates})


@consultant
@require_http_methods(['GET','POST'])
def contact_edit(request, pk):
    contact = get_object_or_404(request.user.managed_contacts, pk=pk)
    # No customer names or link counts are revealed by this shared-edit warning.
    shared = contact.engagement_links.count() > 1
    before = record_state(contact)
    form = forms.ContactForm(request.POST if request.method == 'POST' else None, instance=contact, shared=shared)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            for engagement in Engagement.objects.filter(contact_links__contact=saved).distinct():
                services.audit(engagement, request.user, f'Updated shared contact {saved.pk}.', {'before':before,'after':record_state(saved)})
        return redirect('contact_index')
    return render(request, 'engagements/contact_form.html', {'form':form,'title':'Edit reusable contact','shared':shared})


@consultant
@require_http_methods(['GET','POST'])
def contact_link(request, pk, contact_pk):
    engagement = engagement_for(request.user, pk)
    # Reuse requires explicit contact management access, not an email match.
    contact = get_object_or_404(request.user.managed_contacts.filter(archived=False), pk=contact_pk)
    obj = EngagementContact.objects.filter(engagement=engagement,contact=contact).first() or EngagementContact(engagement=engagement,contact=contact)
    return save_contact_link(request, engagement, obj)


@consultant
@require_http_methods(['GET','POST'])
def contact_link_edit(request, pk):
    obj = get_object_or_404(EngagementContact.objects.filter(engagement__in=engagements_for(request.user)).select_related('engagement','contact'), pk=pk)
    return save_contact_link(request, obj.engagement, obj)


def save_contact_link(request, engagement, obj):
    before = record_state(obj)
    form = forms.EngagementContactForm(request.POST if request.method == 'POST' else None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Serialize primary-contact switches within this engagement.
            Engagement.objects.select_for_update().get(pk=engagement.pk)
            saved = form.save(commit=False)
            if saved.primary and saved.active:
                for previous in engagement.contact_links.filter(primary=True,active=True).exclude(pk=saved.pk):
                    previous.primary = False
                    previous.save(update_fields=['primary'])
                    services.audit(engagement, request.user, f'Contact link {previous.pk} is no longer primary.')
            saved.save()
            services.audit(engagement, request.user, f'Updated engagement contact {saved.pk}. No access or authorization granted.', {'before':before,'after':record_state(saved)})
        return redirect('engagement_contacts',pk=engagement.pk)
    return render(request, 'engagements/contact_form.html', {'form':form,'title':f'Engagement roles: {obj.contact}','engagement':engagement,'link_form':True})
