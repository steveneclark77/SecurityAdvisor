from django.test import SimpleTestCase


class WSGIEntryTests(SimpleTestCase):
    def test_wsgi_exports_django_handler(self):
        from config.wsgi import application
        from django.core.handlers.wsgi import WSGIHandler
        self.assertIsInstance(application,WSGIHandler)
