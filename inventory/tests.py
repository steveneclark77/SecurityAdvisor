from datetime import date
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.test import TestCase,Client
from django.urls import reverse
from engagements.models import Customer,Engagement,Intake,Assessment,Finding
from engagements.services import start_assessment,capture_report
from engagements.forms import FindingForm,IntakeForm
from testsupport.csrf_cases import workflow_fixture
from .models import InventoryItem,InventoryConnection,InventoryFollowUp
from .forms import ItemForm,ConnectionForm,FollowUpForm
from .services import require_customer,intake_followup,capture_inventory


class InventoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=workflow_fixture()
        cls.other=get_user_model().objects.create_user('other-inventory',password='test-only',is_staff=True,is_superuser=True)
        cls.other_customer=Customer.objects.create(name='Other synthetic customer')
        cls.other_customer.assigned_users.add(cls.other)
        cls.foreign=InventoryItem.objects.create(customer=cls.other_customer,kind='provider',name='Private other provider')

    def setUp(self):
        self.client.force_login(self.f.user)

    def test_customer_scoping_and_related_id_tampering(self):
        ids=[('inventory_detail',self.f.customer.pk),('inventory_item_new',self.f.customer.pk),('inventory_item_edit',self.f.operation.pk),('inventory_connection_new',self.f.customer.pk),('inventory_connection_edit',self.f.connection.pk),('inventory_followup_new',self.f.customer.pk),('inventory_followup_edit',self.f.followup.pk)]
        self.client.force_login(self.other)
        for name,pk in ids:
            url=reverse(name,args=[pk])+('?kind=operation' if name=='inventory_item_new' else '')
            self.assertEqual(self.client.get(url).status_code,404)
            self.assertEqual(self.client.post(url,{}).status_code,404)
        self.assertEqual(self.client.post(reverse('inventory_intake_followups',args=[self.f.engagement.pk])).status_code,404)
        self.assertNotContains(self.client.get(reverse('inventory_index')),'Synthetic CSRF Cafe')
        with self.assertRaises(PermissionDenied):
            require_customer(self.other,self.f.customer)
        form=ConnectionForm({'source':self.f.operation.pk,'target':self.foreign.pk,'relationship':'depends_on','details':'Attempted foreign connection','state':'unknown'},customer=self.f.customer,instance=InventoryConnection(customer=self.f.customer))
        self.assertFalse(form.is_valid())
        form=FollowUpForm({'item':self.foreign.pk,'question':'Cross customer','status':'open'},customer=self.f.customer,instance=InventoryFollowUp(customer=self.f.customer))
        self.assertFalse(form.is_valid())
        connection=InventoryConnection(customer=self.f.customer,source=self.f.operation,target=self.foreign,relationship='uses',details='Foreign')
        with self.assertRaises(ValidationError):
            connection.full_clean()

    def test_customer_inventory_shared_across_engagements_and_history_preserved(self):
        second=Engagement.objects.create(customer=self.f.customer,**{**self.f.engagement_data,'title':'Second synthetic engagement'})
        self.assertContains(self.client.get(reverse('engagement_detail',args=[second.pk])),reverse('inventory_detail',args=[self.f.customer.pk]))
        self.assertContains(self.client.get(reverse('inventory_detail',args=[self.f.customer.pk])),'Synthetic biweekly payroll')
        url=reverse('inventory_item_edit',args=[self.f.operation.pk])
        data={'name':'Archived synthetic payroll','state':'unknown','criticality':'unknown','operation_category':'back_office','archived':'on'}
        self.assertEqual(self.client.post(url,data).status_code,302)
        active_page=self.client.get(reverse('inventory_detail',args=[self.f.customer.pk]))
        self.assertNotIn(self.f.operation.pk,[row['item'].pk for row in active_page.context['records']])
        self.assertContains(self.client.get(reverse('inventory_detail',args=[self.f.customer.pk])+'?archived=yes'),'Archived synthetic payroll')
        self.assertTrue(self.f.customer.inventory_events.filter(description__contains='Edit').exists())
        self.assertTrue(InventoryConnection.objects.filter(pk=self.f.connection.pk).exists())

    def test_operations_use_equal_model_for_customer_backoffice_and_ktlo(self):
        for category,name in [('customer','Taking orders'),('back_office','Biweekly payroll'),('ktlo','Patch and restore maintenance')]:
            form=ItemForm({'name':name,'state':'reported','provenance':'Fictional owner at kickoff','criticality':'critical','criticality_reason':'Business cannot meet its deadline','operation_category':category,'schedule':'Recurring deadline','critical_windows':'Before submission','outage_tolerance':'30 minutes','acceptable_data_loss':'One hour','workaround':'Reviewed manual process','financial_impact':'Missed payment costs','availability_impact':'Operations interrupted','reputation_impact':'Trust loss','other_impact':'Employee privacy','impact':5},instance=InventoryItem(customer=self.f.customer,kind='operation'))
            self.assertTrue(form.is_valid(),form.errors)
            operation=form.save()
            self.assertEqual(operation.impact,5)
            self.assertEqual(operation.criticality,'critical')
        unknown=InventoryItem(customer=self.f.customer,kind='device',name='Laptop configurations unknown')
        unknown.full_clean()
        self.assertIsNone(unknown.impact)
        self.assertEqual(unknown.state,'unknown')

    def test_confirmation_requires_provenance_and_review_date(self):
        item=InventoryItem(customer=self.f.customer,kind='provider',name='Payroll provider',state='confirmed')
        with self.assertRaises(ValidationError): item.full_clean()
        item.provenance='Fictional provider configuration review'
        with self.assertRaises(ValidationError): item.full_clean()
        item.last_reviewed=date.today()
        item.full_clean()
        connection=InventoryConnection(customer=self.f.customer,source=self.f.operation,target=self.f.operation,relationship='uses',details='Self reference')
        with self.assertRaises(ValidationError): connection.full_clean()

    def test_assessment_and_report_snapshots_do_not_follow_live_edits(self):
        original=self.f.assessment.inventory_snapshot
        report=capture_report(engagement=self.f.engagement,user=self.f.user)
        before=report.snapshot
        self.f.provider.name='Later provider name'
        self.f.provider.save()
        self.f.assessment.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(self.f.assessment.inventory_snapshot,original)
        self.assertEqual(report.snapshot,before)
        self.assertNotIn('Later provider name',str(original))
        newer=start_assessment(engagement=self.f.engagement,baseline=self.f.baseline,user=self.f.user,profile=self.f.assessment.profile,modifiers=[],rationale='Follow-up with new facts')
        self.assertIn('Later provider name',str(newer.inventory_snapshot))
        self.f.assessment.inventory_snapshot=capture_inventory(self.f.customer)
        with self.assertRaises(ValidationError): self.f.assessment.save()
        legacy=Assessment.objects.create(engagement=self.f.engagement,baseline=self.f.baseline,profile=self.f.assessment.profile,created_by=self.f.user,applicability_rationale='Legacy')
        self.assertContains(self.client.get(reverse('assessment_detail',args=[legacy.pk])),'No inventory snapshot exists')

    def test_finding_links_only_inventory_from_its_own_assessment(self):
        data={**self.f.finding_data,'assessment':self.f.assessment.pk,'inventory_items':[self.f.operation.pk]}
        form=FindingForm(data,instance=Finding(engagement=self.f.engagement),engagement=self.f.engagement)
        self.assertTrue(form.is_valid(),form.errors)
        finding=form.save()
        self.assertEqual(finding.inventory_items.get(),self.f.operation)
        for item in [self.foreign,InventoryItem.objects.create(customer=self.f.customer,kind='device',name='Added after assessment')]:
            form=FindingForm({**data,'inventory_items':[item.pk]},instance=Finding(engagement=self.f.engagement),engagement=self.f.engagement)
            self.assertFalse(form.is_valid())

    def test_intake_information_followups_and_legacy_key_are_preserved(self):
        self.assertEqual(IntakeForm().fields['unknowns'].label,'Information to confirm')
        intake=Intake.objects.create(engagement=self.f.engagement,answers={'unknowns':'Which payroll provider, ISP and security software?'},recommendation={})
        followup=intake_followup(intake,self.f.user)
        self.assertEqual(followup.question,intake.answers['unknowns'])
        self.assertEqual(intake_followup(intake,self.f.user).pk,followup.pk)
        self.assertEqual(InventoryFollowUp.objects.filter(source_intake=intake).count(),1)
        followup.status='resolved'
        with self.assertRaises(ValidationError):followup.full_clean()
        followup.response='Fictional provider and ISP identified'
        followup.save()
        self.client.post(reverse('inventory_intake_followups',args=[self.f.engagement.pk]))
        followup.refresh_from_db()
        self.assertEqual(followup.status,'resolved')
        public=Client(enforce_csrf_checks=True)
        url=reverse('public_response',args=[self.f.intake])
        response=public.get(url)
        self.assertContains(response,'Information to confirm')
        token=public.cookies['csrftoken'].value
        self.assertEqual(public.post(url,{'unknowns':'Missing provider details','intent':'submit','csrfmiddlewaretoken':token},HTTP_ORIGIN='http://testserver').status_code,200)
        self.assertTrue(InventoryFollowUp.objects.filter(customer=self.f.customer,question='Missing provider details').exists())

    def test_explorer_filters_navigation_and_scoped_preview(self):
        url=reverse('inventory_detail',args=[self.f.customer.pk])
        device=InventoryItem.objects.create(customer=self.f.customer,kind='device',name='Synthetic laptop',quantity=2)
        archived=InventoryItem.objects.create(customer=self.f.customer,kind='device',name='Retired laptop',archived=True)
        response=self.client.get(url,{'kind':'device','q':'laptop','state':'unknown','selected':self.foreign.pk})
        self.assertEqual(response.context['selected'],device)
        self.assertNotContains(response,self.foreign.name)
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertContains(response,'Information needed')
        devices=next(c for c in response.context['categories'] if c['key']=='device')
        self.assertEqual(devices['count'],1)
        self.assertIn('q=laptop',devices['url'])
        self.assertIn('state=unknown',devices['url'])
        self.assertNotIn(archived.pk,[row['item'].pk for row in response.context['records']])
        response=self.client.get(url,{'kind':'device','archived':'yes','selected':archived.pk})
        self.assertEqual(response.context['selected'],archived)
        self.assertContains(response,'Archived')
        response=self.client.get(url,{'kind':'physical'})
        self.assertIsNone(response.context['selected'])
        self.assertContains(response,'No records match this view')

    def test_explorer_pages_are_read_only_and_collections_remain_available(self):
        url=reverse('inventory_detail',args=[self.f.customer.pk])
        before=self.f.customer.inventory_events.count()
        for area in ['records','relationships','followups','history','../../other']:
            response=self.client.get(url,{'area':area,'kind':'invalid','state':'invalid','selected':'invalid','page':'invalid'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['kind'],'')
            self.assertEqual(response.context['state'],'')
        self.assertEqual(self.f.customer.inventory_events.count(),before)
        self.assertContains(self.client.get(url,{'area':'relationships'}),self.f.connection.details)
        self.assertContains(self.client.get(url,{'area':'followups'}),self.f.followup.question)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url,{'area':'history','selected':self.f.operation.pk}).status_code,404)

    def test_explorer_pagination_retains_filters(self):
        InventoryItem.objects.bulk_create([InventoryItem(customer=self.f.customer,kind='device',name=f'Laptop {i:03}') for i in range(55)])
        response=self.client.get(reverse('inventory_detail',args=[self.f.customer.pk]),{'kind':'device','q':'Laptop','state':'unknown','page':2})
        self.assertEqual(len(response.context['records']),5)
        self.assertIn('page=1',response.context['previous_url'])
        self.assertIn('kind=device',response.context['previous_url'])
        self.assertEqual(response.context['selected'],response.context['records'][0]['item'])

    def test_saved_record_returns_to_its_category_and_preview(self):
        response=self.client.post(reverse('inventory_item_edit',args=[self.f.operation.pk]),{'name':self.f.operation.name,'state':'unknown','criticality':'unknown','archived':'on'})
        self.assertEqual(response.status_code,302)
        self.assertIn('kind=operation',response.url)
        self.assertIn(f'selected={self.f.operation.pk}',response.url)
        self.assertIn('archived=yes',response.url)

    def test_cancel_returns_only_to_the_same_customer_inventory(self):
        url=reverse('inventory_item_edit',args=[self.f.operation.pk])
        destination=reverse('inventory_detail',args=[self.f.customer.pk])+'?kind=operation&q=payroll&state=unknown&page=1'
        response=self.client.get(url,{'return_to':destination})
        self.assertEqual(response.context['cancel_url'],destination)
        self.assertContains(response,'>Cancel</a>')
        for bad in ['https://example.test/', '//example.test/', reverse('inventory_detail',args=[self.other_customer.pk]), '/admin/']:
            response=self.client.get(url,{'return_to':bad})
            self.assertTrue(response.context['cancel_url'].startswith(reverse('inventory_detail',args=[self.f.customer.pk])+'?'))
        records=self.client.get(reverse('inventory_detail',args=[self.f.customer.pk]),{'kind':'operation','q':'payroll'})
        self.assertIn('return_to=',records.context['records'][0]['actions'][0]['url'])
        self.assertEqual(self.f.customer.inventory_events.count(),0)
