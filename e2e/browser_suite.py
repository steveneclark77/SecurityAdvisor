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
