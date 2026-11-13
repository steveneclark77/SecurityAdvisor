import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from engagements import models as m, services
from library import models as library, services as baseline_services
from inventory.models import InventoryItem, InventoryConnection, InventoryFollowUp


def workflow_fixture():
    call_command('seed_library', verbosity=0)
    password = 'Synthetic-test-password-78!'
    user = get_user_model().objects.create_superuser('csrf-consultant', 'consultant@example.test', password)
    customer = m.Customer.objects.create(name='Synthetic CSRF Cafe')
    customer.assigned_users.add(user)
    engagement_data = dict(title='Synthetic CSRF engagement', scope='Synthetic service and devices', exclusions='No real systems', assessment_authorization='Fictional owner approved synthetic assessment', deliverables='Synthetic report', financial_thresholds='Unknown; investigate', outage_tolerance='Two hours', critical_operations='Orders and payroll', reputation_context='Fictional repeat customers', data_handling='Synthetic data only')
    engagement = m.Engagement.objects.create(customer=customer, **engagement_data)
    person = m.Contact.objects.create(first_name='Alex', last_name='Morgan', email='alex@example.test')
    extra_person = m.Contact.objects.create(first_name='Jordan', last_name='Lee', email='jordan@example.test')
    person.managers.add(user)
    extra_person.managers.add(user)
    link = m.EngagementContact.objects.create(engagement=engagement, contact=person, roles=['business_owner'], primary=True)
    baseline = baseline_services.create_baseline(user=user, version='csrf-approved', coverage_gaps='Synthetic fixture; incomplete baseline')
    baseline_services.approve_baseline(pk=baseline.pk,user=user,note='Synthetic exercise approval')
    baseline.refresh_from_db()
    drafts = [baseline_services.create_baseline(user=user,version=name,coverage_gaps='Synthetic review pending') for name in ['csrf-approve','csrf-revise','csrf-supersede','csrf-replacement']]
    operation = InventoryItem.objects.create(customer=customer,kind='operation',name='Synthetic biweekly payroll',operation_category='back_office',schedule='Every other Tuesday',critical_windows='Submission cutoff',outage_tolerance='One hour near cutoff',state='unknown')
    provider = InventoryItem.objects.create(customer=customer,kind='provider',name='Synthetic payroll provider',state='unknown')
    connection = InventoryConnection.objects.create(customer=customer,source=operation,target=provider,relationship='depends_on',details='Payroll submission depends on the portal')
    followup = InventoryFollowUp.objects.create(customer=customer,item=provider,question='Who administers the provider portal?')
    assessment = services.start_assessment(engagement=engagement, baseline=baseline, user=user, profile='Restaurants, cafés, and food service', modifiers=['Payment processing'], rationale='Synthetic cafe')
    action = assessment.results.filter(control_code='PR-01').first()
    evidence_request = m.EvidenceRequest.objects.create(engagement=engagement,title='Synthetic policy request',instructions='Redacted fixtures only',owner=person)
    evidence = m.Evidence.objects.create(engagement=engagement,title='Synthetic policy',notes='No real data',provenance='Synthetic fixture',collected_on=date.today())
    finding_data = dict(title='Synthetic weak sign-in',condition='Synthetic configuration gap',affected_assets='Fictional identity tenant',business_consequence='Ordering interruption',technical_detail='Synthetic configuration review',financial_impact='Unknown costs',availability_impact='Ordering interruption',reputation_impact='Trust',impact=4,likelihood=3,likelihood_rationale='Synthetic exposed sign-in',confidence='medium',priority='high',priority_rationale='Consultant judgment for fixture',recommendation='Pilot phishing-resistant sign-in',expected_residual_risk='Endpoint compromise remains possible',limitations='Synthetic fixture')
    finding = m.Finding.objects.create(engagement=engagement,assessment=assessment,**finding_data)
    task_data = dict(title='Synthetic sign-in remediation',instructions='Pilot a policy with synthetic identities',owner_id=person.pk,estimated_cost='Pending',estimated_effort='Two hours',verification_plan='Safely reject weak sign-in',authorization='Fictional owner approved change and retest',status='planned')
    task = m.Remediation.objects.create(finding=finding,**task_data)
    task_data['owner'] = task_data.pop('owner_id')
    review = m.Reassessment.objects.create(assessment=assessment,baseline=drafts[0],reason='Synthetic guidance review')
    intake = services.issue_invite(engagement=engagement,user=user,purpose='intake')
    evidence_token = services.issue_invite(engagement=engagement,user=user,purpose='evidence',evidence_request=evidence_request)
    return SimpleNamespace(**locals())


@dataclass
class Submission:
    name: str
    page: str
    target: str
    data: dict
    check: Callable[[], bool]
    status: int = 302
    prepare: Callable[[], object] | None = None


def submissions(f):
    """One valid payload and persisted-outcome assertion per app form operation."""
    url = lambda name,pk=None: reverse(name,args=[pk] if pk is not None else [])
    e = f.engagement.pk
    create = lambda **extra: {**f.finding_data, 'assessment':f.assessment.pk, **extra}
    items = []
    def add(name,page,target,data,check,status=302,prepare=None):
        items.append(Submission(name,page,target,data,check,status,prepare))
    add('create_baseline', '/', url('create_baseline'), {'version':'csrf-created','coverage_gaps':'Synthetic gaps'}, lambda:library.Baseline.objects.filter(version='csrf-created').exists())
    add('approve_baseline',url('baseline_detail',f.drafts[0].pk),url('approve_baseline',f.drafts[0].pk),{'note':'Reviewed synthetic baseline','confirmed':'on'},lambda:library.Baseline.objects.get(pk=f.drafts[0].pk).approved_at is not None)
    add('revise_baseline',url('revise_baseline',f.drafts[1].pk),url('revise_baseline',f.drafts[1].pk),{'version':'csrf-revised','coverage_gaps':'Revised synthetic gaps','revision_note':'Clarify synthetic guidance'},lambda:library.Baseline.objects.get(pk=f.drafts[1].pk).superseded_by_id is not None)
    add('supersede_baseline',url('revise_baseline',f.drafts[2].pk),url('supersede_baseline',f.drafts[2].pk),{'replacement':f.drafts[3].pk,'note':'Use newer fixture'},lambda:library.Baseline.objects.get(pk=f.drafts[2].pk).superseded_by_id==f.drafts[3].pk)
    add('customer_new',url('customer_new'),url('customer_new'),{'name':'New synthetic CSRF customer','synthetic_confirmed':'on'},lambda:m.Customer.objects.filter(name='New synthetic CSRF customer').exists())
    add('engagement_new',url('engagement_new',f.customer.pk),url('engagement_new',f.customer.pk),{**f.engagement_data,'title':'New synthetic CSRF engagement'},lambda:m.Engagement.objects.filter(title='New synthetic CSRF engagement').exists())
    add('engagement_edit',url('engagement_edit',e),url('engagement_edit',e),{**f.engagement_data,'scope':'Updated synthetic scope'},lambda:m.Engagement.objects.get(pk=e).scope=='Updated synthetic scope')
    add('assessment_new',url('assessment_new',e),url('assessment_new',e),{'baseline':f.baseline.pk,'profile':f.assessment.profile,'modifiers':['Payment processing'],'rationale':'Browser-verified synthetic scope'},lambda:m.Assessment.objects.filter(engagement=f.engagement,applicability_rationale='Browser-verified synthetic scope').exists())
    add('action_edit',url('action_edit',f.action.pk),url('action_edit',f.action.pk),{'applicability':'applicable','applicability_reason':'Synthetic critical accounts','implementation':'partial','verification':'failed','confidence':'medium','observation':'Synthetic weaker method accepted','evidence':[f.evidence.pk],'evidence_date':date.today().isoformat()},lambda:m.ActionResult.objects.get(pk=f.action.pk).verification=='failed')
    request_data = dict(title='New synthetic request',instructions='Synthetic evidence only',owner=f.person.pk,status='requested')
    add('request_new',url('request_new',e),url('request_new',e),request_data,lambda:m.EvidenceRequest.objects.filter(title='New synthetic request').exists())
    add('request_edit',url('request_edit',f.evidence_request.pk),url('request_edit',f.evidence_request.pk),{**request_data,'title':'Edited synthetic request'},lambda:m.EvidenceRequest.objects.get(pk=f.evidence_request.pk).title=='Edited synthetic request')
    evidence_data = dict(title='New synthetic evidence',notes='Synthetic notes',provenance='Browser fixture',collected_on=date.today().isoformat(),request=f.evidence_request.pk)
    add('evidence_new',url('evidence_new',e),url('evidence_new',e),evidence_data,lambda:m.Evidence.objects.filter(title='New synthetic evidence').exists())
    add('finding_new',url('finding_new',e),url('finding_new',e),create(title='New synthetic finding',actions=[f.action.pk],evidence=[f.evidence.pk]),lambda:m.Finding.objects.filter(title='New synthetic finding').exists())
    add('finding_edit',url('finding_edit',f.finding.pk),url('finding_edit',f.finding.pk),create(title='Edited synthetic finding'),lambda:m.Finding.objects.get(pk=f.finding.pk).title=='Edited synthetic finding')
    add('task_new',url('task_new',f.finding.pk),url('task_new',f.finding.pk),{**f.task_data,'title':'New synthetic remediation'},lambda:m.Remediation.objects.filter(title='New synthetic remediation').exists())
    add('task_edit',url('task_edit',f.task.pk),url('task_edit',f.task.pk),{**f.task_data,'title':'Edited synthetic remediation'},lambda:m.Remediation.objects.get(pk=f.task.pk).title=='Edited synthetic remediation')
    add('retest_new',url('retest_new',f.task.pk),url('retest_new',f.task.pk),{'tested_on':date.today().isoformat(),'outcome':'passed','procedure_and_result':'Synthetic weak method denied','evidence':[f.evidence.pk],'residual_risk':'Endpoint compromise remains possible'},lambda:m.Remediation.objects.get(pk=f.task.pk).status=='verified')
    add('generate_requests',url('assessment_detail',f.assessment.pk),url('generate_requests',f.assessment.pk),{},lambda:m.EvidenceRequest.objects.filter(assessment=f.assessment).exists())
    add('report_new',url('engagement_detail',e)+'?area=reports',url('report_new',e),{},lambda:m.Report.objects.filter(engagement=f.engagement).exists())
    add('reassessment_edit',url('reassessment_edit',f.review.pk),url('reassessment_edit',f.review.pk),{'status':'planned','decision':'Review synthetic guidance','review_date':date.today().isoformat()},lambda:m.Reassessment.objects.get(pk=f.review.pk).status=='planned')
    for prefix in ['',f'?engagement={e}']:
        name='contact_new'
        contact_data=dict(first_name='New',last_name='Contact'+('Engagement' if prefix else 'Directory'),email='new-eng@example.test' if prefix else 'new-dir@example.test')
        add(name,url(name)+prefix,url(name)+prefix,contact_data,lambda email=contact_data['email']:m.Contact.objects.filter(email=email).exists())
    contact_data=dict(first_name='Alex',last_name='Morgan',email='edited@example.test')
    add('contact_edit',url('contact_edit',f.person.pk),url('contact_edit',f.person.pk),contact_data,lambda:m.Contact.objects.get(pk=f.person.pk).email=='edited@example.test')
    link_url=reverse('contact_link',args=[e,f.extra_person.pk])
    add('contact_link',link_url,link_url,{'roles':['technical'],'active':'on'},lambda:m.EngagementContact.objects.filter(engagement=f.engagement,contact=f.extra_person).exists())
    add('contact_link_edit',url('contact_link_edit',f.link.pk),url('contact_link_edit',f.link.pk),{'roles':['business_owner'],'active':'on','primary':'on','title_override':'Synthetic owner'},lambda:m.EngagementContact.objects.get(pk=f.link.pk).title_override=='Synthetic owner')
    intake_url=url('public_response',f.intake)
    intake_data={'activities':'Synthetic cafe, payroll and vendor payments','unknowns':'Providers and device configuration need confirmation','modifiers':['Payment processing']}
    add('public_response',intake_url,intake_url,{**intake_data,'intent':'save'},lambda:m.Invite.objects.get(token_digest=hashlib.sha256(f.intake.encode()).hexdigest()).draft_answers.get('activities')==intake_data['activities'],200)
    add('public_response',intake_url,intake_url,{**intake_data,'intent':'submit'},lambda:m.Intake.objects.filter(engagement=f.engagement).exists(),200)
    evidence_url=url('public_response',f.evidence_token)
    add('public_response',evidence_url,evidence_url,{**evidence_data,'title':'Public synthetic evidence'},lambda:m.Evidence.objects.filter(title='Public synthetic evidence').exists(),200)
    for purpose in ['intake','evidence']:
        add('invite_new',url('engagement_detail',e)+('?area=intake' if purpose=='intake' else f'?area=evidence&collection=requests&selected={f.evidence_request.pk}'),url('invite_new',e),{'purpose':purpose,'request_id':f.evidence_request.pk},lambda purpose=purpose:m.Invite.objects.filter(engagement=f.engagement,purpose=purpose).count()==2,200)
    add('revoke_invites',url('engagement_detail',e)+'?area=links',url('revoke_invites',e),{},lambda:not m.Invite.objects.filter(engagement=f.engagement,used_at__isnull=True,expires_at__gt=timezone.now()).exists())
    customer_id=f.customer.pk
    item_url=url('inventory_item_new',customer_id)+'?kind=operation'
    item_data={'name':'New synthetic payroll operation','state':'unknown','criticality':'unknown','operation_category':'back_office','schedule':'Biweekly payroll cutoff'}
    add('inventory_item_new',item_url,item_url,item_data,lambda:InventoryItem.objects.filter(customer=f.customer,name='New synthetic payroll operation').exists())
    for kind,extra in [
        ('provider',{'vendor_product':'Fictional payroll service','access_method':'Separate portal; administrator unknown','data_handling':'Employee PII categories only'}),
        ('device',{'quantity':2,'operating_system':'Fictional laptop OS','security_configuration':'Antivirus and firewall configuration unknown'}),
        ('software',{'vendor_product':'QuickBooks and Dropbox examples','access_method':'SSO status unknown'}),
        ('network',{'vendor_product':'ISP and router to confirm','security_configuration':'Bundled protections unknown'}),
        ('physical',{'description':'Alarm and camera service','access_method':'Vendor remote access to confirm'}),
        ('data',{'data_handling':'Employee PII; full card data versus tokens to confirm','exposures':['employee_pii','payments']}),
    ]:
        target=url('inventory_item_new',customer_id)+'?kind='+kind
        name='New synthetic '+kind+' inventory'
        add('inventory_item_new',target,target,{'name':name,'state':'unknown','criticality':'unknown',**extra},lambda name=name:InventoryItem.objects.filter(customer=f.customer,name=name).exists())
    edit_url=url('inventory_item_edit',f.operation.pk)
    add('inventory_item_edit',edit_url,edit_url,{**item_data,'name':'Updated synthetic payroll operation'},lambda:InventoryItem.objects.get(pk=f.operation.pk).name=='Updated synthetic payroll operation')
    connection_data={'source':f.operation.pk,'target':f.provider.pk,'relationship':'depends_on','details':'Synthetic provider portal connection','state':'unknown'}
    add('inventory_connection_new',url('inventory_connection_new',customer_id),url('inventory_connection_new',customer_id),connection_data,lambda:InventoryConnection.objects.filter(customer=f.customer,details='Synthetic provider portal connection').exists())
    edit_url=url('inventory_connection_edit',f.connection.pk)
    add('inventory_connection_edit',edit_url,edit_url,{**connection_data,'details':'Updated synthetic connection'},lambda:InventoryConnection.objects.get(pk=f.connection.pk).details=='Updated synthetic connection')
    followup_data={'item':f.provider.pk,'question':'Which payroll service is used?','status':'open'}
    add('inventory_followup_new',url('inventory_followup_new',customer_id),url('inventory_followup_new',customer_id),followup_data,lambda:InventoryFollowUp.objects.filter(customer=f.customer,question='Which payroll service is used?').exists())
    edit_url=url('inventory_followup_edit',f.followup.pk)
    add('inventory_followup_edit',edit_url,edit_url,{**followup_data,'status':'resolved','response':'Synthetic provider identified'},lambda:InventoryFollowUp.objects.get(pk=f.followup.pk).status=='resolved')
    add('inventory_intake_followups',url('engagement_detail',e)+'?area=intake',url('inventory_intake_followups',e),{},lambda:InventoryFollowUp.objects.filter(customer=f.customer,question='Legacy provider details to confirm').exists(),prepare=lambda:m.Intake.objects.create(engagement=f.engagement,answers={'unknowns':'Legacy provider details to confirm'},recommendation={'profile':f.assessment.profile,'modifiers':[]}))
    add('inventory_walkthrough_operations',url('inventory_detail',customer_id)+'?kind=operation&walkthrough=yes',url('inventory_walkthrough_operations',customer_id),{'owner':f.person.pk},lambda:InventoryItem.objects.filter(customer=f.customer,name='Device maintenance and backup recovery',owner=f.person).exists())
    return items
