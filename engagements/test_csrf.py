"""CSRF must accept legitimate submissions as well as reject hostile requests."""
import inspect
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from testsupport.csrf_cases import workflow_fixture, submissions


class FormCsrfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = workflow_fixture()

    def exercise(self, secure):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.fixture.user)
        origin = ('https' if secure else 'http') + '://testserver'
        cases = submissions(self.fixture)
        completed = 0
        for case in cases:
            with self.subTest(form=case.name, target=case.target):
                page = browser.get(case.page, secure=secure)
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page['Referrer-Policy'], 'same-origin')
                self.assertContains(page, 'name="csrfmiddlewaretoken"')
                token = browser.cookies['csrftoken'].value
                good = {**case.data, 'csrfmiddlewaretoken':token}
                for label, data, headers in [
                    ('missing token',case.data,{'HTTP_ORIGIN':origin}),
                    ('wrong token',{**good,'csrfmiddlewaretoken':'x'*32},{'HTTP_ORIGIN':origin}),
                    ('null origin',good,{'HTTP_ORIGIN':'null'}),
                    ('foreign origin',good,{'HTTP_ORIGIN':'https://untrusted.example'}),
                ]:
                    with self.subTest(rejected=label):
                        self.assertEqual(browser.post(case.target,data,secure=secure,**headers).status_code,403)
                # Exercise HTTPS's strict Referer fallback too, without an Origin.
                headers = {'HTTP_REFERER':origin+case.page} if secure else {'HTTP_ORIGIN':origin}
                response = browser.post(case.target,good,secure=secure,**headers)
                self.assertEqual(response.status_code,case.status, response.content[:1500])
                self.assertTrue(case.check(),f'{case.name} returned success without the expected persisted change')
                completed += 1
        self.assertEqual(completed,len(cases),'Some protected submissions did not complete.')
        print(f'CSRF matrix: {len(cases)} valid form operations and {4*len(cases)} rejected requests ({"HTTPS Referer" if secure else "HTTP Origin"}).')

    def test_all_application_forms_http(self):
        self.exercise(secure=False)

    def test_all_application_forms_https_referer(self):
        self.exercise(secure=True)

    def test_new_mutating_routes_must_have_submission_coverage(self):
        covered = {case.name for case in submissions(self.fixture)}
        discovered = set()
        def walk(patterns):
            for route in patterns:
                if isinstance(route, URLResolver):
                    if route.app_name != 'admin':
                        walk(route.url_patterns)
                elif isinstance(route, URLPattern):
                    callback = inspect.unwrap(route.callback)
                    if callback.__module__ not in ['engagements.views','library.views']:
                        continue
                    source = inspect.getsource(callback)
                    if '@require_POST' in source or ('@require_http_methods' in source and 'POST' in source):
                        discovered.add(route.name)
        walk(get_resolver().url_patterns)
        self.assertEqual(discovered,covered,'Add a valid payload and outcome check for every new application POST route.')
