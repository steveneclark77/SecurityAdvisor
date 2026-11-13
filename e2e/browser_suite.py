"""Real form navigation, cookies, CSRF tokens, headers, and persistence checks.

Run: E2E_BROWSER=chromium python manage.py test e2e.browser_suite
Ordinary Django test discovery intentionally does not require browser tooling.
"""
import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.db import connections
from playwright.sync_api import sync_playwright, expect
from engagements import models as m
from library import models as library
from testsupport.csrf_cases import workflow_fixture, submissions


class BrowserForms(StaticLiveServerTestCase):
    def _fixture_teardown(self):
        # SQLite flush uses DELETE, unlike PostgreSQL TRUNCATE. Temporarily
        # remove history guards only while destroying this synthetic test data.
        from django.db import connection
        import importlib
        guards = importlib.import_module('news.migrations.0004_version_immutability')
        if connection.vendor != 'sqlite':
            return super()._fixture_teardown()
        editor = connection.schema_editor(atomic=False)
        guards.uninstall(None, editor)
        try:
            return super()._fixture_teardown()
        finally:
            guards.install(None, editor)

    def setUp(self):
        self.media = tempfile.TemporaryDirectory(prefix='securityadvisor-browser-media-')
        self.addCleanup(self.media.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=self.media.name))
        self.fixture = workflow_fixture()
        self.db_pool = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(self.db_pool.shutdown)
        self.playwright = sync_playwright().start()
        self.addCleanup(self.playwright.stop)
        self.engine = os.environ.get('E2E_BROWSER','chromium')
        if self.engine not in ['chromium','webkit']:
            raise ValueError('E2E_BROWSER must be chromium or webkit')
        options = {'headless':True}
        if os.environ.get('E2E_EXECUTABLE_PATH'):
            options['executable_path'] = os.environ['E2E_EXECUTABLE_PATH']
        self.browser = getattr(self.playwright,self.engine).launch(**options)
        self.context = self.browser.new_context()
        self.context.set_default_timeout(15000)
        self.context.tracing.start(screenshots=True,snapshots=True,sources=True)
        self.page = self.context.new_page()
        self.posts = []
        self.page.on('response',lambda response:self.posts.append((response.url,response.status)) if response.request.method=='POST' else None)

    def tearDown(self):
        artifacts = Path(os.environ.get('E2E_ARTIFACT_DIR','test-artifacts')) / self.engine
        artifacts.mkdir(parents=True,exist_ok=True)
        try:
            self.page.screenshot(path=str(artifacts/(self._testMethodName+'.png')),full_page=True)
            self.context.tracing.stop(path=str(artifacts/(self._testMethodName+'.zip')))
        finally:
            self.context.close()
            self.browser.close()
            self.playwright.stop()
            self.db_pool.submit(connections.close_all).result()
            super().tearDown()

    def db(self, operation):
        # Playwright's synchronous API owns an event loop on the test thread.
        # Run ORM assertions on a separate synchronous thread, retaining Django's
        # async-safety guard rather than setting DJANGO_ALLOW_ASYNC_UNSAFE.
        return self.db_pool.submit(operation).result()

    def visit(self, path):
        response = self.page.goto(self.live_server_url+path)
        self.assertEqual(response.status,200)
        self.assertEqual(response.header_value('referrer-policy'),'same-origin')
        return response

    def submit(self, form, button, target):
        absolute = self.live_server_url+target
        with self.page.expect_navigation(wait_until='load'), self.page.expect_response(lambda response:response.request.method=='POST' and response.url==absolute) as captured:
            button.click()
        response = captured.value
        self.assertNotEqual(response.status,403,f'CSRF rejected {target}')
        self.assertEqual(response.request.header_value('origin'),self.live_server_url)
        return response

    def login(self):
        self.visit(reverse('admin:login'))
        self.page.locator('[name=username]').fill(self.fixture.user.username)
        self.page.locator('[name=password]').fill(self.fixture.password)
        form = self.page.locator('#login-form')
        self.assertEqual(self.submit(form,form.locator('[type=submit]'),reverse('admin:login')).status,302)

    def test_intake_save_reload_finalize_and_reuse(self):
        path = reverse('public_response',args=[self.fixture.intake])
        self.visit(path)
        self.page.get_by_label('Activities:').fill('Synthetic cafe with payroll and vendor payments')
        self.page.get_by_label('Information to confirm:').fill('Providers and laptop configurations need confirmation')
        form = self.page.locator('form')
        response = self.submit(form,self.page.get_by_role('button',name='Save progress',exact=True),path)
        self.assertEqual(response.status,200)
        expect(self.page.get_by_text('Draft saved.',exact=False)).to_be_visible()
        self.page.reload()
        expect(self.page.get_by_label('Activities:')).to_have_value('Synthetic cafe with payroll and vendor payments')
        invite = self.db(lambda:m.Invite.objects.get(token_digest=hashlib.sha256(self.fixture.intake.encode()).hexdigest()))
        self.assertIsNone(invite.used_at)
        self.assertFalse(self.db(lambda:m.Intake.objects.exists()))
        response = self.submit(self.page.locator('form'),self.page.get_by_role('button',name='Submit final response',exact=True),path)
        self.assertEqual(response.status,200)
        expect(self.page.get_by_role('heading',name='Response received')).to_be_visible()
        expect(self.page.get_by_role('heading',name='Corrections and additions')).to_be_visible()
        expect(self.page.locator('.guidance-panel')).to_have_css('border-left-width', '3px')
        expect(self.page.get_by_text('You cannot edit this submission directly.',exact=False)).to_be_visible()
        expect(self.page.get_by_text('Our team will work with you to correct or add to the information used for your assessment.',exact=False)).to_be_visible()
        expect(self.page.locator('form')).to_have_count(0)
        self.assertEqual(self.db(lambda:m.Intake.objects.get().answers['unknowns']),'Providers and laptop configurations need confirmation')
        self.assertEqual(self.page.goto(self.live_server_url+path).status,404)
        # The invitation URL must not become a referrer on another origin.
        self.visit(reverse('public_response',args=[self.fixture.evidence_token]))
        destination = 'http://external.example.test/privacy-check'
        self.page.route(destination,lambda route:route.fulfill(status=200,body='Synthetic external destination'))
        self.page.evaluate("url => { const a=document.createElement('a'); a.href=url; a.textContent='Privacy check'; document.body.append(a); }",destination)
        with self.page.expect_request(destination) as outgoing:
            self.page.get_by_role('link',name='Privacy check').click()
        self.assertIsNone(outgoing.value.header_value('referer'))

    def test_public_evidence_upload(self):
        path = reverse('public_response',args=[self.fixture.evidence_token])
        self.visit(path)
        for name,value in {'title':'Browser evidence upload','notes':'Synthetic configuration','provenance':'Browser fixture','collected_on':date.today().isoformat()}.items():
            self.page.locator(f'[name="{name}"]').fill(value)
        self.page.locator('[type=file]').set_input_files({'name':'synthetic.txt','mimeType':'text/plain','buffer':b'Synthetic redacted evidence'})
        response = self.submit(self.page.locator('form'),self.page.get_by_role('button',name='Submit final response',exact=True),path)
        self.assertEqual(response.status,200)
        evidence = self.db(lambda:m.Evidence.objects.get(title='Browser evidence upload'))
        self.assertEqual(evidence.file.read(),b'Synthetic redacted evidence')
        evidence.file.close()
        self.db(self.fixture.evidence_request.refresh_from_db)
        self.assertEqual(self.fixture.evidence_request.status,'received')
        self.assertEqual(self.page.goto(self.live_server_url+path).status,404)

    def test_all_authenticated_app_form_operations(self):
        self.login()
        cases = [case for case in submissions(self.fixture) if case.name!='public_response']
        completed = 0
        for case in cases:
            with self.subTest(form=case.name,target=case.target):
                if case.prepare:
                    self.db(case.prepare)
                self.visit(case.page)
                matching = []
                for form in self.page.locator('form').all():
                    action = form.evaluate("f => { const u=new URL(f.getAttribute('action') || location.href, location.href); return u.pathname+u.search; }")
                    if action != case.target:
                        continue
                    purpose = form.locator('[name=purpose]')
                    if purpose.count() and purpose.input_value()!=case.data.get('purpose'):
                        continue
                    request_id = form.locator('[name=request_id]')
                    if request_id.count() and request_id.input_value()!=str(case.data.get('request_id')):
                        continue
                    matching.append(form)
                self.assertEqual(len(matching),1,f'Could not uniquely identify form {case.name}')
                form = matching[0]
                for name,value in case.data.items():
                    fields = form.locator(f'[name="{name}"]')
                    if not fields.count():
                        continue  # Server ignores e.g. request_id on intake invitations.
                    field = fields.first
                    tag = field.evaluate('e=>e.tagName.toLowerCase()')
                    kind = field.get_attribute('type')
                    if kind=='hidden':
                        self.assertEqual(field.input_value(),str(value))
                    elif kind in ['checkbox','radio']:
                        values = [str(v) for v in value] if isinstance(value,list) else [str(value)]
                        for choice in fields.all():
                            choice.set_checked(choice.get_attribute('value') in values or (len(values)==1 and values[0]=='on'))
                    elif tag=='select':
                        field.select_option([str(v) for v in value] if isinstance(value,list) else str(value))
                    else:
                        field.fill(str(value))
                if case.name=='evidence_new':
                    form.locator('[type=file]').set_input_files({'name':'synthetic.txt','mimeType':'text/plain','buffer':b'Synthetic consultant attachment'})
                button = form.locator('button[type=submit],button:not([type]),input[type=submit]').first
                expect(button).to_be_enabled()
                response = self.submit(form,button,case.target)
                self.assertEqual(response.status,case.status)
                self.assertTrue(self.db(case.check),f'{case.name} did not persist the expected result')
                completed += 1
        self.assertEqual(completed,len(cases),'Some browser form operations did not complete.')
        self.assertFalse(any(status==403 for _,status in self.posts))
        print(f'{self.engine}: actual browser submissions passed for {len(cases)} authenticated app operations plus login.')

    def test_admin_control_actions_profiles_modifiers_password_and_logout(self):
        self.login()
        control = self.db(lambda:library.Control.objects.first())
        path = reverse('admin:library_control_change',args=[control.pk])
        self.visit(path)
        self.page.locator('[name=recommendation]').fill('Synthetic browser-reviewed recommendation')
        self.page.locator('textarea[name^="actions-"][name$="-instruction"]').first.fill('Synthetic browser-reviewed action')
        form = self.page.locator('#control_form')
        self.assertEqual(self.submit(form,form.locator('input[name="_save"]'),path).status,302)
        self.db(control.refresh_from_db)
        self.assertEqual(control.recommendation,'Synthetic browser-reviewed recommendation')
        self.assertEqual(self.db(lambda:control.actions.first().instruction),'Synthetic browser-reviewed action')
        for model,label in [('profile','Synthetic browser profile'),('modifier','Synthetic browser modifier')]:
            path=reverse(f'admin:library_{model}_add')
            self.visit(path)
            self.page.locator('[name=name]').fill(label)
            form=self.page.locator(f'#{model}_form')
            self.assertEqual(self.submit(form,form.locator('input[name="_save"]'),path).status,302)
            cls = library.Profile if model=='profile' else library.Modifier
            self.assertTrue(self.db(lambda:cls.objects.filter(name=label).exists()))
        path=reverse('admin:password_change')
        self.visit(path)
        for name,value in {'old_password':self.fixture.password,'new_password1':'New-synthetic-password-89!','new_password2':'New-synthetic-password-89!'}.items():
            self.page.locator(f'[name={name}]').fill(value)
        form=self.page.locator('form').filter(has=self.page.locator('[name=old_password]'))
        self.assertEqual(self.submit(form,form.locator('[type=submit]'),path).status,302)
        self.db(self.fixture.user.refresh_from_db)
        self.assertTrue(self.fixture.user.check_password('New-synthetic-password-89!'))
        form=self.page.locator('#logout-form')
        self.assertEqual(self.submit(form,form.locator('button'),reverse('admin:logout')).status,200)
        self.page.goto(self.live_server_url+reverse('engagement_index'))
        self.assertIn('/admin/login/',self.page.url)

    def test_stale_prelogin_token_rejected_then_reload_recovers(self):
        path = reverse('public_response',args=[self.fixture.intake])
        self.visit(path)
        original_page = self.page
        original_page.get_by_label('Activities:').fill('Synthetic unsaved draft')
        # Another tab logs in, rotating the shared CSRF cookie legitimately.
        self.page = self.context.new_page()
        self.login()
        self.page.close()
        self.page = original_page
        with self.page.expect_navigation(wait_until='load'), self.page.expect_response(lambda r:r.request.method=='POST') as captured:
            self.page.get_by_role('button',name='Save progress',exact=True).click()
        self.assertEqual(captured.value.status,403)
        self.assertFalse(self.db(lambda:m.Intake.objects.exists()))
        # Reloading the original invitation gets a fresh masked token; it must work.
        self.visit(path)
        self.page.get_by_label('Activities:').fill('Synthetic recovered draft')
        response = self.submit(self.page.locator('form'),self.page.get_by_role('button',name='Save progress',exact=True),path)
        self.assertEqual(response.status,200)
        self.page.reload()
        expect(self.page.get_by_label('Activities:')).to_have_value('Synthetic recovered draft')


    def test_news_sources_issue_triage_and_append_only_review(self):
        from news.models import Source, Issue, Scan, Review
        self.login()
        path = reverse('admin:news_source_add')
        self.visit(path)
        form = self.page.locator('#source_form')
        save = form.locator('input[name="_save"]')
        expect(save).to_be_disabled()
        for name, value in {'name': 'Synthetic browser feed', 'url': 'https://synthetic-browser.example.test/', 'feed_url': 'https://www.bleepingcomputer.com/feed/'}.items():
            self.page.locator(f'[name={name}]').fill(value)
        expect(save).to_be_enabled()
        self.assertEqual(self.submit(form, save, path).status, 302)
        source = self.db(lambda: Source.objects.get(name='Synthetic browser feed'))
        def create_issue():
            from django.utils import timezone
            from news.versioning import create_version
            scan = Scan.objects.create(source=source, feed_url=source.feed_url, status='success')
            issue = Issue.objects.create(source=source, first_scan=scan, identity='synthetic-browser', last_seen_at=timezone.now())
            create_version(issue=issue, expected_version_id=None, content={'name': 'Synthetic practice', 'url': 'https://www.bleepingcomputer.com/synthetic'}, actor=None, origin='publisher_ingestion', change_reason='Synthetic discovery')
            issue.refresh_from_db()
            return issue
        issue = self.db(create_issue)
        self.visit(reverse('admin:news_issue_change', args=[issue.pk]))
        self.page.get_by_role('link', name='Create next version').click()
        path = reverse('admin:news_issueversion_add') + f'?issue={issue.pk}&base_version={issue.current_version_id}'
        self.page.locator('[name=remediation]').fill('Review synthetic identity configuration')
        self.page.locator('[name=severity]').select_option('medium')
        form = self.page.locator('#issueversion_form')
        expect(form.locator('input[name="_save"]')).to_be_disabled()
        self.page.locator('[name=change_reason]').fill('Synthetic new recommendation')
        self.page.locator('[name=references-0-source]').select_option(str(source.pk))
        self.page.locator('[name=references-0-source_url]').fill('https://www.bleepingcomputer.com/synthetic-advisory')
        self.assertEqual(self.submit(form, form.locator('input[name="_save"]'), path).status, 302)
        self.db(issue.refresh_from_db)
        self.assertEqual(self.db(lambda: issue.current_version.version_number), 2)
        self.assertEqual(self.db(lambda: issue.current_version.references.get().source_url), 'https://www.bleepingcomputer.com/synthetic-advisory')
        path = reverse('admin:news_review_add')
        self.visit(path)
        self.page.locator('[name=issue]').select_option(str(issue.pk))
        self.page.locator('[name=issue_version]').select_option(str(issue.current_version_id))
        self.page.locator('[name=decision]').select_option('add')
        self.page.locator('[name=rationale]').fill('Synthetic manual relevance review')
        expect(self.page.locator('#review_form input[name="_save"]')).to_be_disabled()
        self.page.locator('[name=proposed_guidance]').fill('Consider identity guidance in a future reviewed baseline')
        form = self.page.locator('#review_form')
        self.assertEqual(self.submit(form, form.locator('input[name="_save"]'), path).status, 302)
        review = self.db(lambda: Review.objects.get(issue=issue))
        self.assertEqual(review.actor_id, self.fixture.user.pk)
        self.assertEqual(review.issue_snapshot['severity'], 'medium')
        self.assertEqual(review.issue_snapshot['remediation'], 'Review synthetic identity configuration')
        self.visit(reverse('admin:news_review_change', args=[review.pk]))
        expect(self.page.locator('input[name="_save"]')).to_have_count(0)


    def test_shared_styles_cover_consultant_public_responsive_and_print_views(self):
        self.login()
        self.visit(reverse('engagement_index'))
        expect(self.page.locator('body')).to_have_css('font-size', '16px')
        expect(self.page.locator('header')).to_have_css('background-color', 'rgb(21, 45, 70)')
        expect(self.page.locator('a.button').first).to_have_css('padding-left', '14px')
        self.visit('/')
        expect(self.page.locator('.detail-table th').first).to_have_css('padding-left', '10px')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        expect(self.page.locator('main')).to_have_css('padding-left', '12px')
        expect(self.page.locator('.detail-table th').first).to_have_css('padding-left', '6px')
        self.page.emulate_media(media='print')
        expect(self.page.locator('header')).to_be_hidden()
        expect(self.page.locator('.button').first).to_be_hidden()
        expect(self.page.locator('body')).to_have_css('background-color', 'rgb(255, 255, 255)')
        self.page.emulate_media(media='screen')
        self.visit(reverse('public_response', args=[self.fixture.intake]))
        expect(self.page.locator('body')).to_have_css('font-size', '16px')
        expect(self.page.locator('body')).to_have_css('max-width', '760px')


    def test_engagement_journey_guidance_actions_and_responsive_layout(self):
        def fresh():
            f = self.fixture
            customer = m.Customer.objects.create(name='Synthetic Harbor Cafe')
            customer.assigned_users.add(f.user)
            engagement = m.Engagement.objects.create(customer=customer, **{**f.engagement_data, 'title': 'Initial security improvement exercise'})
            m.EngagementContact.objects.create(engagement=engagement, contact=f.person, roles=['business_owner'], active=True)
            m.Intake.objects.create(engagement=engagement, answers={'activities': 'Synthetic cafe'}, recommendation={'profile': 'Restaurants, cafés, and food service', 'modifiers': ['Payment processing'], 'reason': 'Synthetic customer report; review required.'})
            return engagement
        engagement = self.db(fresh)
        self.login()
        self.page.set_viewport_size({'width': 1536, 'height': 1100})
        path = reverse('engagement_detail', args=[engagement.pk])
        self.visit(path)
        rail = self.page.get_by_role('navigation', name='Engagement workflow')
        expect(rail.locator('.journey-action')).to_have_count(7)
        expect(rail.locator('.is-recommended')).to_have_count(1)
        expect(rail.locator('[data-step=inventory]')).to_have_class('journey-step is-recommended')
        expect(rail.get_by_role('link', name='Review customer intake')).to_have_text('Review')
        expect(rail.get_by_role('link', name='Start inventory and operations')).to_have_text('Start')
        expect(self.page.locator('.journey-context a, .journey-context button, .journey-context input')).to_have_count(0)
        self.assertEqual(len(set(rail.locator('a').evaluate_all('links => links.map(a => a.href)'))), 7)
        for button in rail.locator('a').all():
            expect(button).to_have_css('background-color', 'rgb(255, 255, 255)')
        marker = rail.locator('[data-step=inventory]')
        self.assertEqual(marker.evaluate("e => getComputedStyle(e, '::after').borderTopWidth"), '5px')
        artifacts = Path('test-artifacts') / self.engine
        artifacts.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(artifacts / 'journey-desktop.png'), full_page=True)
        # Selecting any area is allowed, including reporting before assessment.
        rail.get_by_role('link', name='Start reports').click()
        expect(self.page.locator('#work-reports')).to_be_visible()
        expect(self.page.get_by_role('button', name='Capture executive and technical report')).to_be_visible()
        self.visit(path)
        rail.get_by_role('link', name='Review customer intake').click()
        expect(self.page.locator('#work-intake')).to_be_visible()
        expect(self.page.get_by_text('Synthetic cafe', exact=True)).to_be_visible()
        # Small screens stack the same rail and guidance without clipping actions.
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.visit(path)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        expect(self.page.get_by_role('link', name='Start inventory and operations')).to_be_visible()
        self.page.screenshot(path=str(artifacts / 'journey-mobile.png'), full_page=True)

    def test_inventory_explorer_filters_preview_and_responsive_layout(self):
        from inventory.models import InventoryItem
        device=self.db(lambda: InventoryItem.objects.create(customer=self.fixture.customer,kind='device',name='Synthetic cafe laptops',quantity=2))
        self.login()
        self.page.set_viewport_size({'width':1600,'height':1000})
        path=reverse('inventory_detail',args=[self.fixture.customer.pk])
        self.visit(path)
        categories=self.page.get_by_role('navigation',name='Inventory sections')
        categories.get_by_role('link',name='Devices').click()
        expect(self.page.get_by_role('link',name='Add device / equipment group',exact=True)).to_be_visible()
        self.page.get_by_role('link',name='Synthetic cafe laptops',exact=True).click()
        preview=self.page.get_by_role('complementary',name='Record preview')
        expect(preview.get_by_role('heading',name='Synthetic cafe laptops')).to_be_visible()
        expect(preview.get_by_text('Information needed',exact=True).first).to_be_visible()
        expect(preview.get_by_role('link',name='Edit')).to_have_count(0)
        artifacts=Path('test-artifacts') / self.engine
        artifacts.mkdir(parents=True,exist_ok=True)
        self.page.screenshot(path=str(artifacts / 'inventory-desktop.png'),full_page=True)
        self.page.get_by_role('searchbox',name='Search records').fill('no such record')
        self.page.get_by_role('button',name='Apply filters').click()
        expect(self.page.get_by_text('No records match this view.',exact=False)).to_be_visible()
        self.page.get_by_role('searchbox',name='Search records').fill('')
        self.page.get_by_role('button',name='Apply filters').click()
        categories.get_by_role('link',name='Relationships').click()
        expect(self.page.get_by_role('link',name='Connect records',exact=True)).to_be_visible()
        categories.get_by_role('link',name='Information to confirm').click()
        expect(self.page.get_by_role('link',name='Request missing information',exact=True)).to_be_visible()
        self.visit(path+'?kind=device&selected='+str(device.pk))
        self.page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        expect(preview.get_by_role('heading',name='Synthetic cafe laptops')).to_be_visible()
        self.page.screenshot(path=str(artifacts / 'inventory-mobile.png'),full_page=True)

    def test_shared_record_browsers_assessment_evidence_and_contacts(self):
        self.login()
        self.page.set_viewport_size({'width':1600,'height':1000})
        artifacts=Path('test-artifacts') / self.engine
        artifacts.mkdir(parents=True,exist_ok=True)
        preview=self.page.get_by_role('complementary',name='Record preview')
        assessment=reverse('assessment_detail',args=[self.fixture.assessment.pk])+'?q=PR-01&selected='+str(self.fixture.action.pk)
        self.visit(assessment)
        expect(self.page.get_by_role('link',name='Investigate and record result',exact=True)).to_have_count(1)
        self.page.get_by_label('Verification',exact=True).select_option('failed')
        self.page.get_by_role('button',name='Apply filters').click()
        expect(self.page.get_by_text('No records match this view.',exact=False)).to_be_visible()
        self.page.get_by_label('Verification',exact=True).select_option('')
        self.page.get_by_role('button',name='Apply filters').click()
        self.page.locator('.record-table-wrap tbody a').first.click()
        expect(preview.get_by_role('heading',name='Verification procedure',exact=True)).to_be_visible()
        self.page.screenshot(path=str(artifacts / 'assessment-desktop.png'),full_page=True)
        evidence=reverse('engagement_detail',args=[self.fixture.engagement.pk])+'?area=evidence&collection=requests&selected='+str(self.fixture.evidence_request.pk)
        self.visit(evidence)
        expect(preview.get_by_role('button',name='Create scoped submission link',exact=True)).to_be_visible()
        tabs=self.page.get_by_role('navigation',name='Evidence collections')
        tabs.get_by_role('link',name='Evidence register').click()
        expect(preview.get_by_role('heading',name=self.fixture.evidence.title,exact=True)).to_be_visible()
        expect(self.page.get_by_role('link',name='Record evidence',exact=True)).to_have_count(1)
        tabs.get_by_role('link',name='Findings').click()
        expect(preview.get_by_role('heading',name=self.fixture.finding.title,exact=True)).to_be_visible()
        expect(self.page.get_by_role('link',name='Create finding',exact=True)).to_have_count(1)
        self.page.screenshot(path=str(artifacts / 'evidence-findings-desktop.png'),full_page=True)
        contacts=reverse('engagement_contacts',args=[self.fixture.engagement.pk])
        self.visit(contacts)
        expect(preview.get_by_text('Business owner',exact=True)).to_be_visible()
        expect(preview.get_by_role('link',name='Edit roles, primary status, or unlink',exact=True)).to_have_count(1)
        expect(preview.get_by_role('link',name='Edit / archive shared contact',exact=True)).to_have_count(1)
        self.page.screenshot(path=str(artifacts / 'contacts-desktop.png'),full_page=True)
        self.page.get_by_role('navigation',name='Contact collections').get_by_role('link',name='Available to link',exact=True).click()
        expect(preview.get_by_role('link',name='Link Jordan Lee',exact=True)).to_be_visible()
        self.visit(reverse('contact_index'))
        self.page.get_by_role('searchbox',name='Search records').fill('Jordan')
        self.page.get_by_role('button',name='Apply filters').click()
        expect(preview.get_by_role('heading',name='Jordan Lee',exact=True)).to_be_visible()
        expect(self.page.locator('.record-table-wrap tbody tr')).to_have_count(1)
        self.page.set_viewport_size({'width':390,'height':844})
        for name,path in [('assessment',assessment),('evidence-findings',evidence),('contacts',contacts)]:
            self.visit(path)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),name)
            self.page.locator('.record-table-wrap tbody a').first.click()
            expect(preview).to_be_in_viewport()
            self.page.screenshot(path=str(artifacts / (name+'-mobile.png')),full_page=True)

    def test_contact_owner_add_link_refresh_and_single_assignment(self):
        self.login()
        path=reverse('inventory_item_edit',args=[self.fixture.operation.pk])
        self.visit(path)
        owner=self.page.locator('select[name=owner]')
        expect(owner).to_be_visible()
        expect(owner.locator('option[value="'+str(self.fixture.person.pk)+'"]')).to_have_count(1)
        self.page.locator('[name=notes]').fill('Jordan assists with payroll; one contact is accountable.')
        with self.page.expect_popup() as opened:
            self.page.get_by_role('link',name='Add contact (opens in a new tab)',exact=True).click()
        popup=opened.value
        popup.wait_for_load_state()
        popup.locator('[name=first_name]').fill('Taylor')
        popup.locator('[name=last_name]').fill('Owner')
        popup.locator('[name=email]').fill('taylor-owner@example.test')
        popup.locator('[name=link_engagement]').select_option(str(self.fixture.engagement.pk))
        popup.get_by_role('button',name='Save contact',exact=True).click()
        popup.locator('[name=roles][value=technical]').check()
        popup.locator('[name=active]').check()
        popup.get_by_role('button',name='Save contact',exact=True).click()
        expect(popup.get_by_role('heading',name='Linked contacts',exact=True)).to_be_visible()
        popup.close()
        expect(self.page.locator('[name=notes]')).to_have_value('Jordan assists with payroll; one contact is accountable.')
        self.page.get_by_role('button',name='Refresh contacts',exact=True).click()
        expect(self.page.get_by_role('status')).to_contain_text('Contacts updated')
        contact_id=self.db(lambda: m.Contact.objects.get(email='taylor-owner@example.test').pk)
        owner.select_option(str(contact_id))
        self.page.get_by_role('button',name='Save inventory record',exact=True).click()
        self.db(self.fixture.operation.refresh_from_db)
        self.assertEqual(self.fixture.operation.owner_id,contact_id)
        self.assertIn('Jordan assists',self.fixture.operation.notes)
        # The same picker and notes are present in engagement-scoped work.
        self.visit(reverse('request_new',args=[self.fixture.engagement.pk]))
        expect(self.page.locator('select[name=owner]')).to_be_visible()
        expect(self.page.locator('[name=notes]')).to_be_visible()
        self.page.locator('[name=title]').fill('Owned synthetic request')
        self.page.locator('[name=instructions]').fill('Synthetic evidence only')
        self.page.locator('select[name=owner]').select_option(str(contact_id))
        self.page.locator('[name=notes]').fill('Alex supports collection.')
        self.page.get_by_role('button',name='Save',exact=True).click()
        self.assertEqual(self.db(lambda: m.EvidenceRequest.objects.get(title='Owned synthetic request').owner_id),contact_id)

    def test_contextual_choices_field_help_dialogs_and_owner_icons(self):
        self.login()
        self.page.set_viewport_size({'width':1280,'height':1000})
        self.visit(reverse('inventory_item_new',args=[self.fixture.customer.pk])+'?kind=operation')
        expect(self.page.locator('[name=operation_category] option[value=""]')).to_have_text('Select an operation category')
        expect(self.page.locator('[name=owner] option[value=""]')).to_have_text('Unassigned')
        expect(self.page.get_by_role('button',name='Help for Exposures',exact=True)).to_have_count(1)
        expect(self.page.get_by_role('link',name='Add contact (opens in a new tab)',exact=True)).to_be_visible()
        refresh=self.page.get_by_role('button',name='Refresh contacts',exact=True)
        expect(refresh).to_have_text('↻')
        self.assertLessEqual(refresh.bounding_box()['width'],40)
        expect(self.page.get_by_role('button',name='Save inventory record',exact=True)).to_be_disabled()
        info=self.page.get_by_role('button',name='Help for Owner',exact=True)
        expect(info).to_be_enabled()
        before=len(self.posts)
        info.click()
        dialog=self.page.get_by_role('dialog',name='Owner help',exact=True)
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text('one accountable contact')
        expect(self.page.locator('#id_owner_helptext')).to_be_visible()
        self.page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        expect(info).to_be_focused()
        self.assertEqual(len(self.posts),before)
        expect(self.page.locator('#id_owner_helptext')).not_to_be_visible()
        self.page.get_by_role('button',name='Help for Notes',exact=True).click()
        self.page.get_by_role('dialog',name='Notes help',exact=True).get_by_role('button',name='Close',exact=True).click()
        artifacts=Path('test-artifacts') / self.engine
        artifacts.mkdir(parents=True,exist_ok=True)
        self.page.screenshot(path=str(artifacts / 'contextual-form-help.png'),full_page=True)
        # Public forms use the same enhancement and keep legitimate submission controls.
        self.visit(reverse('public_response',args=[self.fixture.intake]))
        self.page.get_by_role('button',name='Help for Information to confirm',exact=True).click()
        expect(self.page.get_by_role('dialog',name='Information to confirm help',exact=True)).to_be_visible()
        self.page.keyboard.press('Escape')
        # Admin widgets share the renderer/help controller, including dynamically added inlines.
        self.visit(reverse('admin:library_control_add'))
        self.page.get_by_role('button',name='Help for Recommendation',exact=True).click()
        expect(self.page.get_by_role('dialog',name='Recommendation help',exact=True)).to_contain_text('High-level outcome')
        self.page.keyboard.press('Escape')
        self.page.locator('.add-row a').click()
        self.assertGreater(self.page.locator('button[aria-label="Help for Verification"]').count(),0)
