"""Prevent inline CSS from returning to any first-party template."""
from pathlib import Path
import re
from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class SharedStyleTests(SimpleTestCase):
    def test_all_first_party_templates_keep_css_in_stylesheets(self):
        templates = []
        root = Path(settings.BASE_DIR).resolve()
        templates.extend((root / 'templates').rglob('*.html'))
        for app in apps.get_app_configs():
            app_root = Path(app.path).resolve()
            if app_root.parent == root:
                templates.extend((app_root / 'templates').rglob('*.html'))
        self.assertTrue(templates)
        inline_css = re.compile(r'<\s*style\b|\sstyle\s*=', re.IGNORECASE)
        for path in templates:
            with self.subTest(template=str(path.relative_to(root))):
                self.assertNotRegex(path.read_text(), inline_css, 'Use the shared static stylesheets.')
