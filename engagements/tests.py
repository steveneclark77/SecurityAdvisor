import hashlib
import tempfile
from datetime import timedelta
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from library.models import Control
from library.services import create_baseline, approve_baseline
from . import forms, services
from .models import Customer, Engagement, Assessment, ActionResult, EvidenceRequest, Evidence, Finding, Remediation, Retest, Invite, Intake, AuditEvent, Report, Reassessment, Contact, EngagementContact


class EngagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_library', verbosity=0)
        cls.user = get_user_model().objects.create_user('consultant',password='test-only-password',is_staff=True)
        cls.other = get_user_model().objects.create_user('other-consultant',password='test-only-password',is_staff=True)
        cls.customer = Customer.objects.create(name='Synthetic Harbor Cafe')
        cls.customer.assigned_users.add(cls.user)
        cls.engagement = Engagement.objects.create(customer=cls.customer, **cls.engagement_data())
        cls.person = Contact.objects.create(first_name='Alex',last_name='Morgan',email='alex@example.test')
        cls.person.managers.add(cls.user)
        EngagementContact.objects.create(engagement=cls.engagement,contact=cls.person,roles=['business_owner'],primary=True)
        cls.baseline = create_baseline(user=cls.user, version='test-v1', coverage_gaps='Synthetic exercise; detailed mappings and framework coverage incomplete.')
        approve_baseline(pk=cls.baseline.pk,user=cls.user,note='Synthetic baseline review with documented gaps.')
        cls.baseline.refresh_from_db()
        cls.assessment = services.start_assessment(engagement=cls.engagement,baseline=cls.baseline,user=cls.user,profile='Restaurants, cafés, and food service',modifiers=['Payment processing'],rationale='Restaurant and hosted payments; review each exclusion.')
        cls.evidence = Evidence.objects.create(engagement=cls.engagement,title='Synthetic policy export',notes='Made-up MFA configuration, no secrets.',provenance='Synthetic test fixture',collected_on=timezone.localdate())
        cls.finding = Finding.objects.create(engagement=cls.engagement,assessment=cls.assessment,**cls.finding_data())
        cls.task = Remediation.objects.create(finding=cls.finding,title='Require phishing-resistant sign-in',instructions='Pilot a test policy.',owner='Synthetic owner',estimated_cost='Estimate pending',estimated_effort='Two hours',verification_plan='Reject a weaker sign-in method using a test account.')

    @staticmethod
    def engagement_data():
        return dict(title='Synthetic initial review',scope='Fictional email, ordering, and devices.',exclusions='No intrusive tests.',legacy_contact_note='Fictional owner',assessment_authorization='Fictional owner approved configuration review only.',deliverables='Summary and improvement plan',financial_thresholds='Levels 1–5 to be confirmed; unknown for this fixture.',outage_tolerance='Two hours during service',critical_operations='Ordering and payments',reputation_context='Repeat local customers',data_handling='Synthetic data only; retention details pending.')

    @staticmethod
    def finding_data():
        return dict(title='Weak privileged sign-in',condition='Synthetic administrator can use a weak method.',affected_assets='Fictional identity tenant',business_consequence='Ordering administration could be compromised.',technical_detail='Synthetic configuration review only.',financial_impact='Fraud and recovery costs; amounts unknown',availability_impact='Ordering interruption',reputation_impact='Customer trust',impact=4,likelihood=3,likelihood_rationale='Exposed sign-in with weak authentication in the fixture.',confidence='medium',priority='high',priority_rationale='Consultant judgment based on critical administration.',recommendation='Require phishing-resistant MFA with tested recovery.',expected_residual_risk='Session theft and device compromise still possible.',limitations='Synthetic fixture, not a real assessment.')

    def setUp(self):
        self.client.force_login(self.user)

    def test_customer_creation_assigns_creator_and_requires_synthetic_confirmation(self):
        response = self.client.post(reverse('customer_new'), {'name':'Synthetic workshop'})
        self.assertFalse(Customer.objects.filter(name='Synthetic workshop').exists())
        response = self.client.post(reverse('customer_new'), {'name':'Synthetic workshop','synthetic_confirmed':'on'})
        self.assertEqual(response.status_code,302)
        customer = Customer.objects.get(name='Synthetic workshop')
        self.assertEqual(list(customer.assigned_users.all()),[self.user])
        response = self.client.post(reverse('engagement_new',args=[customer.pk]),self.engagement_data())
        self.assertEqual(response.status_code,302)
        self.assertTrue(customer.engagements.exists())

    def test_customer_boundaries_cover_every_record_route(self):
        report = services.capture_report(engagement=self.engagement,user=self.user)
        request = EvidenceRequest.objects.create(engagement=self.engagement,title='Synthetic export',instructions='Redact identifiers.',owner='Fictional owner')
        review = Reassessment.objects.create(assessment=self.assessment,baseline=self.baseline,reason='Test only')
        routes = [('engagement_detail',self.engagement.pk),('engagement_edit',self.engagement.pk),('assessment_new',self.engagement.pk),('assessment_detail',self.assessment.pk),('action_edit',self.assessment.results.first().pk),('request_new',self.engagement.pk),('request_edit',request.pk),('evidence_new',self.engagement.pk),('evidence_download',self.evidence.pk),('finding_new',self.engagement.pk),('finding_edit',self.finding.pk),('task_new',self.finding.pk),('task_edit',self.task.pk),('retest_new',self.task.pk),('report_detail',report.pk),('reassessment_edit',review.pk)]
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        for name, pk in routes:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name,args=[pk])).status_code,404)
                self.assertEqual(self.client.post(reverse(name,args=[pk]),{}).status_code,404)
        for name in ['invite_new','revoke_invites','report_new']:
            self.assertEqual(self.client.post(reverse(name,args=[self.engagement.pk]),{}).status_code,404)
        self.assertNotContains(self.client.get(reverse('engagement_index')),'Synthetic Harbor Cafe')
        with self.assertRaises(PermissionDenied):
            services.capture_report(engagement=self.engagement,user=self.other)
        with self.assertRaises(PermissionDenied):
            services.start_assessment(engagement=self.engagement,baseline=self.baseline,user=self.other,profile='x',modifiers=[],rationale='x')

    def test_assessment_requires_approval_and_uses_frozen_applicability(self):
        draft = create_baseline(user=self.user,version='draft',coverage_gaps='Pending review')
        with self.assertRaises(ValidationError):
            services.start_assessment(engagement=self.engagement,baseline=draft,user=self.user,profile='Restaurants, cafés, and food service',modifiers=[],rationale='test')
        with self.assertRaises(ValidationError):
            services.start_assessment(engagement=self.engagement,baseline=self.baseline,user=self.user,profile='Not a captured profile',modifiers=[],rationale='test')
        result = self.assessment.results.filter(control_code='PR-01').first()
        captured = result.guidance
        Control.objects.filter(code='PR-01').update(recommendation='Changed later')
        result.refresh_from_db()
        self.assertEqual(captured,result.guidance)
        self.assertTrue(self.assessment.results.filter(control_code='PAY-01',applicability='applicable').exists())
        self.assertTrue(self.assessment.results.filter(control_code='SW-01',applicability='excluded').exists())
        self.assertTrue(self.assessment.results.filter(implementation='unknown',verification='not_tested').exists())

    def test_action_verification_needs_evidence_and_records_actor(self):
        result = self.assessment.results.filter(control_code='PR-01').first()
        data = dict(applicability='applicable',applicability_reason='Critical accounts',implementation='partial',verification='failed',confidence='medium',observation='Synthetic weak method remained available.')
        self.assertEqual(self.client.post(reverse('action_edit',args=[result.pk]),data).status_code,400)
        data.update(evidence=[self.evidence.pk],evidence_date=timezone.localdate().isoformat())
        self.assertEqual(self.client.post(reverse('action_edit',args=[result.pk]),data).status_code,302)
        result.refresh_from_db()
        self.assertEqual(result.verified_by,self.user)
        self.assertEqual(result.verification,'failed')
        self.assertContains(self.client.get(reverse('assessment_detail',args=[self.assessment.pk]),{'selected':result.pk}),'Synthetic weak method')

    def test_cross_engagement_relationships_rejected(self):
        other_customer = Customer.objects.create(name='Synthetic isolated company')
        other_customer.assigned_users.add(self.other)
        other_engagement = Engagement.objects.create(customer=other_customer,**self.engagement_data())
        foreign_evidence = Evidence.objects.create(engagement=other_engagement,title='Private fixture',notes='Other customer',provenance='Fixture',collected_on=timezone.localdate())
        foreign_request = EvidenceRequest.objects.create(engagement=other_engagement,title='Other request',instructions='Test',owner='Other')
        result = self.assessment.results.first()
        data = dict(applicability='applicable',applicability_reason='test',implementation='unknown',verification='not_tested',confidence='unknown',evidence=[foreign_evidence.pk])
        form = forms.ActionResultForm(data,instance=result,engagement=self.engagement)
        self.assertFalse(form.is_valid())
        form = forms.EvidenceForm(dict(title='Test',notes='Test',provenance='Test',collected_on=timezone.localdate(),request=foreign_request.pk),engagement=self.engagement)
        self.assertFalse(form.is_valid())
        data = {**self.finding_data(),'assessment':self.assessment.pk,'evidence':[foreign_evidence.pk]}
        form = forms.FindingForm(data,instance=Finding(engagement=self.engagement),engagement=self.engagement)
        self.assertFalse(form.is_valid())

    def test_intake_link_saves_draft_expires_and_cannot_access_customer_records(self):
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='intake')
        invite = Invite.objects.get(token_digest=hashlib.sha256(raw.encode()).hexdigest())
        self.assertNotEqual(raw,invite.token_digest)
        public = Client()
        url = reverse('public_response',args=[raw])
        response = public.get(url)
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'Synthetic Harbor Cafe')
        self.assertIn('no-store',response['Cache-Control'])
        response = public.post(url,{'industry':'Restaurants, cafés, and food service','activities':'Synthetic cafe','modifiers':['Payment processing'],'intent':'save'})
        self.assertContains(response,'Draft saved')
        self.assertFalse(Intake.objects.exists())
        self.assertContains(public.get(url),'Synthetic cafe')
        response = public.post(url,{'industry':'Restaurants, cafés, and food service','modifiers':['Payment processing'],'intent':'submit'})
        self.assertContains(response,'Response received')
        self.assertEqual(Intake.objects.get().recommendation['modifiers'],['Payment processing'])
        self.assertEqual(public.get(url).status_code,404)
        self.assertEqual(public.post(url,{}).status_code,404)
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='intake')
        Invite.objects.filter(used_at__isnull=True).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(public.get(reverse('public_response',args=[raw])).status_code,404)

    def test_public_evidence_is_scoped_and_attachments_are_private(self):
        request = EvidenceRequest.objects.create(engagement=self.engagement,title='Synthetic MFA export',instructions='Redacted fixture only',owner='Fictional owner')
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='evidence',evidence_request=request)
        url = reverse('public_response',args=[raw])
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            public = Client()
            response = public.post(url,{'title':'Synthetic sign-in policy','notes':'Fictional configuration','provenance':'Synthetic export','collected_on':timezone.localdate(),'file':SimpleUploadedFile('policy.txt',b'Synthetic redacted policy',content_type='text/plain')})
            self.assertEqual(response.status_code,200)
            evidence = Evidence.objects.get(request=request)
            self.assertTrue(Path(directory,evidence.file.name).exists())
            self.assertNotIn('policy.txt',evidence.file.name)
            self.assertEqual(public.get(reverse('evidence_download',args=[evidence.pk])).status_code,302)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(reverse('evidence_download',args=[evidence.pk])).status_code,404)
            self.client.force_login(self.user)
            response = self.client.get(reverse('evidence_download',args=[evidence.pk]))
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response['Content-Disposition'])
            self.assertEqual(b''.join(response.streaming_content), b'Synthetic redacted policy')
            self.assertEqual(public.get(url).status_code,404)
            self.assertEqual(public.get('/private-evidence/'+evidence.file.name).status_code,404)

    def test_evidence_upload_validation(self):
        for filename,content in [('payload.html',b'<script>bad</script>'),('fake.pdf',b'not a PDF'),('large.txt',b'x'*(5*1024*1024+1)),('binary.txt',b'\x00\xff')]:
            with self.subTest(filename=filename):
                with self.assertRaises(ValidationError):
                    forms.validate_evidence_file(SimpleUploadedFile(filename,content))

    def test_finding_unknown_risk_and_acceptance_rules(self):
        finding = Finding(engagement=self.engagement,assessment=self.assessment,**self.finding_data())
        finding.impact = None
        with self.assertRaises(ValidationError): finding.full_clean()
        finding.priority = 'unrated'
        finding.full_clean()
        finding.risk_acceptance = 'Fictional owner accepts risk'
        with self.assertRaises(ValidationError): finding.full_clean()
        finding.acceptance_review = timezone.localdate()+timedelta(days=30)
        finding.full_clean()

    def test_remediation_requires_authorization_and_verified_dependencies(self):
        self.task.status = 'implemented'
        with self.assertRaises(ValidationError): self.task.full_clean()
        self.task.authorization = 'Fictional owner approved test policy change.'
        self.task.status = 'verified'
        with self.assertRaises(ValidationError): self.task.full_clean()
        dependency = Remediation.objects.create(finding=self.finding,title='Test recovery first',instructions='Test',owner='Owner',estimated_cost='0',estimated_effort='1h',verification_plan='Test')
        data = {field.name:getattr(self.task,field.name) for field in self.task._meta.fields if field.name not in ['id','finding']}
        data.update(status='in_progress',dependencies=[dependency.pk])
        form = forms.RemediationForm(data,instance=self.task,engagement=self.engagement)
        self.assertFalse(form.is_valid())

    def test_retest_pass_verifies_and_failure_reopens_without_rewriting_report(self):
        self.task.authorization = 'Synthetic owner approved change and tests.'
        self.task.save()
        report = services.capture_report(engagement=self.engagement,user=self.user)
        original = report.snapshot
        data = dict(tested_on=timezone.localdate(),outcome='passed',procedure_and_result='Synthetic weaker sign-in denied; recovery succeeded.',evidence=[self.evidence.pk],residual_risk='Session theft remains possible.')
        response = self.client.post(reverse('retest_new',args=[self.task.pk]),data)
        self.assertEqual(response.status_code,302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status,'verified')
        report.refresh_from_db()
        self.assertEqual(original,report.snapshot)
        data.update(outcome='failed',procedure_and_result='Synthetic regression detected.')
        self.assertEqual(self.client.post(reverse('retest_new',args=[self.task.pk]),data).status_code,302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status,'reopened')
        self.task.status = 'verified'
        with self.assertRaises(ValidationError): self.task.full_clean()
        self.assertEqual(Retest.objects.filter(task=self.task).count(),2)

    def test_report_contains_uncertainty_and_is_preserved(self):
        report = services.capture_report(engagement=self.engagement,user=self.user)
        response = self.client.get(reverse('report_detail',args=[report.pk]))
        self.assertContains(response,'Executive summary')
        self.assertContains(response,'Investigation results, exclusions, and unknowns')
        self.assertContains(response,'Synthetic fixture, not a real assessment.')
        self.finding.title = 'Changed later'
        self.finding.save()
        self.assertNotContains(self.client.get(reverse('report_detail',args=[report.pk])),'Changed later')
        with self.assertRaises(ValidationError): report.save()

    def test_reassessment_matches_changed_relevant_controls_and_preserves_assessment(self):
        before = self.assessment.results.first().guidance
        Control.objects.filter(code='PR-01').update(recommendation='New draft recommendation')
        baseline = create_baseline(user=self.user,version='test-v2',coverage_gaps='Still incomplete')
        self.assertFalse(Reassessment.objects.exists())
        approve_baseline(pk=baseline.pk,user=self.user,note='Reviewed changes')
        review = Reassessment.objects.get(assessment=self.assessment)
        self.assertIn('PR-01',review.reason)
        self.assertEqual(before,self.assessment.results.first().guidance)
        response = self.client.post(reverse('reassessment_edit',args=[review.pk]),{'status':'dismissed','decision':''})
        self.assertEqual(response.status_code,400)
        response = self.client.post(reverse('reassessment_edit',args=[review.pk]),{'status':'planned','decision':'Review sign-in policy with customer','review_date':timezone.localdate()+timedelta(days=7)})
        self.assertEqual(response.status_code,302)

    def test_csrf_and_mutation_methods(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for route in ['invite_new','report_new','revoke_invites']:
            url = reverse(route,args=[self.engagement.pk])
            self.assertEqual(self.client.get(url).status_code,405)
            self.assertEqual(client.post(url,{}).status_code,403)
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='intake')
        self.assertEqual(client.post(reverse('public_response',args=[raw]),{}).status_code,403)

    def test_generated_evidence_requests_are_repeatable_and_skip_exclusions(self):
        url = reverse('generate_requests',args=[self.assessment.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url).status_code,302)
        requests = self.engagement.evidence_requests
        self.assertFalse(requests.filter(control_code='SW-01').exists())
        self.assertTrue(requests.filter(control_code='PAY-01').exists())
        count = requests.count()
        request = requests.first()
        request.instructions = 'Consultant edited instructions'
        request.save()
        self.client.post(url)
        request.refresh_from_db()
        self.assertEqual(requests.count(),count)
        self.assertEqual(request.instructions,'Consultant edited instructions')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code,404)

    def test_browser_assessment_finding_and_task_creation(self):
        response = self.client.post(reverse('assessment_new',args=[self.engagement.pk]),{
            'baseline':self.baseline.pk,'profile':'Restaurants, cafés, and food service',
            'modifiers':['Payment processing'],'rationale':'Confirmed hosted payment scope.',
        })
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Assessment')
        assessment = Assessment.objects.latest('pk')
        result = assessment.results.filter(control_code='PR-01').first()
        url = reverse('finding_new',args=[self.engagement.pk])+'?action='+str(result.pk)
        self.assertContains(self.client.get(url),'Protect business accounts')
        data = {**self.finding_data(),'assessment':assessment.pk,'actions':[result.pk],'evidence':[self.evidence.pk]}
        self.assertEqual(self.client.post(url,data).status_code,302)
        finding = Finding.objects.latest('pk')
        self.assertEqual(finding.actions.get(),result)
        task_url = reverse('task_new',args=[finding.pk])
        self.assertContains(self.client.get(task_url),'Require phishing-resistant MFA')
        response = self.client.post(task_url,dict(title='Synthetic MFA policy',instructions='Pilot a policy with test identities.',owner='Fictional owner',estimated_cost='Pending',estimated_effort='2 hours',verification_plan='Try a weaker sign-in method.',status='planned'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(reverse('report_new',args=[self.engagement.pk])).status_code,302)
        self.assertTrue(AuditEvent.objects.filter(engagement=self.engagement).exists())

    def test_contact_step_replaces_text_input_and_gates_assessment(self):
        response = self.client.get(reverse('engagement_new',args=[self.customer.pk]))
        self.assertNotContains(response,'name="legacy_contact_note"')
        self.assertNotContains(response,'name="contact"')
        response = self.client.post(reverse('engagement_new',args=[self.customer.pk]),self.engagement_data())
        created = Engagement.objects.latest('pk')
        self.assertRedirects(response,reverse('engagement_contacts',args=[created.pk]))
        self.assertFalse(created.contact_links.exists())
        with self.assertRaises(ValidationError):
            services.start_assessment(engagement=created,baseline=self.baseline,user=self.user,profile='Restaurants, cafés, and food service',modifiers=[],rationale='Test')
        self.assertContains(self.client.get(reverse('engagement_contacts',args=[created.pk])),'add an active contact first')
        self.assertContains(self.client.get(reverse('engagement_contacts',args=[self.engagement.pk])),'Legacy contact note requiring review')

    def test_contact_creation_methods_and_duplicate_warning(self):
        url = reverse('contact_new')
        data = dict(first_name='Jordan',last_name='Lee',title='Engineer',organization='Synthetic contractor')
        self.client.post(url,data)
        self.assertFalse(Contact.objects.filter(first_name='Jordan').exists())
        data.update(office_phone='+44 (0)20 1234 5678 ext 42')
        self.assertEqual(self.client.post(url,data).status_code,302)
        person = Contact.objects.get(first_name='Jordan')
        self.assertEqual(list(person.managers.all()),[self.user])
        self.assertFalse(person.engagement_links.exists())
        response = self.client.post(url,data)
        self.assertContains(response,'possibly matching accessible contact')
        self.assertEqual(Contact.objects.filter(first_name='Jordan').count(),1)
        self.client.post(url,{**data,'confirm_duplicate':'on'})
        self.assertEqual(Contact.objects.filter(first_name='Jordan').count(),2)
        form = forms.ContactForm({**data,'preferred_method':'email'})
        self.assertFalse(form.is_valid())

    def test_contact_can_link_multiple_engagements_and_primary_switches(self):
        second = Engagement.objects.create(customer=self.customer,**self.engagement_data())
        url = reverse('contact_link',args=[second.pk,self.person.pk])
        self.assertEqual(self.client.post(url,{'roles':['technical','remediation'],'primary':'on','active':'on','title_override':'Contract engineer'}).status_code,302)
        self.assertEqual(self.person.engagement_links.count(),2)
        link = second.contact_links.get()
        self.assertEqual(link.title_override,'Contract engineer')
        self.assertNotEqual(self.engagement.contact_links.get().title_override,'Contract engineer')
        person = Contact.objects.create(first_name='Sam',last_name='Rivera',email='sam@example.test')
        person.managers.add(self.user)
        self.assertEqual(self.client.post(reverse('contact_link',args=[second.pk,person.pk]),{'roles':['business_owner'],'primary':'on','active':'on'}).status_code,302)
        self.assertEqual(second.contact_links.filter(primary=True,active=True).count(),1)
        link.refresh_from_db()
        self.assertFalse(link.primary)

    def test_shared_contact_edit_confirmation_archiving_and_snapshots(self):
        second = Engagement.objects.create(customer=self.customer,**self.engagement_data())
        EngagementContact.objects.create(engagement=second,contact=self.person,roles=['technical'])
        report = services.capture_report(engagement=self.engagement,user=self.user)
        url = reverse('contact_edit',args=[self.person.pk])
        response = self.client.get(url)
        self.assertContains(response,'linked to multiple engagements')
        data = dict(first_name='Alex',last_name='Morgan',email='updated@example.test')
        self.client.post(url,data)
        self.person.refresh_from_db()
        self.assertEqual(self.person.email,'alex@example.test')
        self.assertEqual(self.client.post(url,{**data,'confirm_shared_edit':'on','archived':'on'}).status_code,302)
        self.person.refresh_from_db()
        self.assertTrue(self.person.archived)
        self.assertEqual(self.person.email,'updated@example.test')
        self.assertFalse(self.engagement.active_contacts.exists())
        report.refresh_from_db()
        self.assertEqual(report.snapshot['contacts'][0]['email'],'alex@example.test')
        self.assertTrue(AuditEvent.objects.filter(engagement=second,description__contains='shared contact').exists())

    def test_shared_contacts_do_not_reveal_other_clients_or_grant_reuse(self):
        foreign = Customer.objects.create(name='Secret other company')
        foreign.assigned_users.add(self.other)
        other_engagement = Engagement.objects.create(customer=foreign,**self.engagement_data())
        EngagementContact.objects.create(engagement=other_engagement,contact=self.person,roles=['technical'])
        hidden = Contact.objects.create(first_name='Hidden',last_name='Person',email='hidden@example.test')
        hidden.managers.add(self.other)
        self.assertNotContains(self.client.get(reverse('contact_index')),'Hidden Person')
        self.assertNotContains(self.client.get(reverse('contact_edit',args=[self.person.pk])),'Secret other company')
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('engagement_contacts',args=[other_engagement.pk])),'Alex Morgan')
        self.assertNotContains(self.client.get(reverse('contact_index')),'Synthetic Harbor Cafe')
        self.assertEqual(self.client.get(reverse('contact_edit',args=[self.person.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('contact_link',args=[other_engagement.pk,self.person.pk]),{'roles':['technical'],'active':'on'}).status_code,404)
        self.assertEqual(self.client.get(reverse('engagement_contacts',args=[self.engagement.pk])).status_code,404)
        response = self.client.post(reverse('contact_new'),dict(first_name='Alex',last_name='Newperson',email='alex@example.test'))
        self.assertContains(response,'possibly matching accessible contact')
        private = Contact.objects.create(first_name='Private',last_name='Contractor',email='private@example.test')
        private.managers.add(self.user)
        response = self.client.post(reverse('contact_new'),dict(first_name='Private',last_name='Contractor',email='private@example.test'))
        self.assertEqual(response.status_code,302)
        self.assertNotContains(self.client.get(reverse('contact_index')),'Secret other company')

    def test_contact_unlink_retains_person_history_and_requires_post_csrf(self):
        link = self.engagement.contact_links.get()
        url = reverse('contact_link_edit',args=[link.pk])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(url,{'roles':['business_owner']}).status_code,403)
        self.assertEqual(self.client.post(url,{'roles':['business_owner']}).status_code,302)
        link.refresh_from_db()
        self.assertFalse(link.active)
        self.assertTrue(Contact.objects.filter(pk=self.person.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(engagement=self.engagement,description__contains='engagement contact').exists())

    def test_intake_origin_policy_and_csrf_protected_save_submit(self):
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='intake')
        url = reverse('public_response',args=[raw])
        browser = Client(enforce_csrf_checks=True)
        response = browser.get(url)
        self.assertContains(response,'name="referrer" content="same-origin"')
        self.assertEqual(response['Referrer-Policy'],'same-origin')
        token = browser.cookies['csrftoken'].value
        payload = {'activities':'Synthetic cafe and outsourced payroll','intent':'save','csrfmiddlewaretoken':token}
        for origin in ['null','https://untrusted.example']:
            self.assertEqual(browser.post(url,payload,HTTP_ORIGIN=origin).status_code,403)
        self.assertEqual(browser.post(url,{'activities':'Missing token','intent':'save'},HTTP_ORIGIN='http://testserver').status_code,403)
        invite = Invite.objects.get(token_digest=hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(invite.draft_answers,{})
        self.assertIsNone(invite.used_at)
        response = browser.post(url,payload,HTTP_ORIGIN='http://testserver')
        self.assertContains(response,'Draft saved')
        self.assertContains(browser.get(url),'Synthetic cafe and outsourced payroll')
        invite.refresh_from_db()
        self.assertIsNone(invite.used_at)
        response = browser.post(url,{**payload,'intent':'submit'},HTTP_ORIGIN='http://testserver')
        self.assertContains(response,'Response received')
        self.assertEqual(Intake.objects.get(engagement=self.engagement).answers['activities'],'Synthetic cafe and outsourced payroll')
        self.assertEqual(browser.get(url).status_code,404)

    def test_evidence_origin_policy_preserves_csrf_on_https(self):
        evidence_request = EvidenceRequest.objects.create(engagement=self.engagement,title='Synthetic record',instructions='Redacted data only',owner='Fictional')
        raw = services.issue_invite(engagement=self.engagement,user=self.user,purpose='evidence',evidence_request=evidence_request)
        url = reverse('public_response',args=[raw])
        browser = Client(enforce_csrf_checks=True)
        response = browser.get(url,secure=True)
        self.assertContains(response,'name="referrer" content="same-origin"')
        token = browser.cookies['csrftoken'].value
        payload = {'title':'Synthetic export','notes':'Fictional data','provenance':'Test fixture','collected_on':timezone.localdate(),'csrfmiddlewaretoken':token}
        self.assertEqual(browser.post(url,payload,secure=True,HTTP_ORIGIN='null').status_code,403)
        # HTTPS browsers without an Origin header still need a same-origin Referer.
        self.assertEqual(browser.post(url,payload,secure=True,HTTP_REFERER='https://untrusted.example/').status_code,403)
        response = browser.post(url,payload,secure=True,HTTP_REFERER='https://testserver'+url)
        self.assertContains(response,'Response received')
        self.assertTrue(Evidence.objects.filter(request=evidence_request,title='Synthetic export').exists())
