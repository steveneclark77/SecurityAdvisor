"""Guard against accidentally widening the browser skip policy."""
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from .browser_selection import BROWSER_INDEPENDENT,changed_files,decision,main,select


class BrowserSelectionTests(TestCase):
    def test_only_explicit_modified_transports_can_skip(self):
        for path in BROWSER_INDEPENDENT:
            self.assertFalse(select([('M',path),('M','VERSION')])[0])
        self.assertFalse(select([('M',p) for p in BROWSER_INDEPENDENT])[0])

    def test_every_uncertain_change_forces_browsers_even_with_safe_change(self):
        for path in ['news/views.py','news/forms.py','news/models.py','news/analysis.py',
                     'news/tests.py','config/settings.py','templates/base.html','library/static/library/forms.js',
                     'inventory/static/inventory/layout.css','requirements.txt','README.md',
                     '.github/workflows/application-tests.yml','ci/browser_selection.py','new_module.py']:
            self.assertTrue(select([('M','news/analysis_provider.py'),('M',path)])[0],path)
        for status in ['A','D','R100','C100','T','?']:
            self.assertTrue(select([(status,'news/analysis_provider.py')])[0])
        for changes in [[],[('M','VERSION')]]:
            self.assertTrue(select(changes)[0])

    def test_other_events_and_git_failure_run_everything(self):
        with patch('ci.browser_selection.changed_files',side_effect=RuntimeError) as diff:
            self.assertTrue(decision('push')[0]);self.assertTrue(decision('workflow_dispatch')[0])
            diff.assert_not_called()
            self.assertTrue(decision('pull_request')[0])
        for base,head in [('', ''),('bad','a'*40)]:
            self.assertTrue(decision('pull_request',base,head)[0])

    def test_null_delimited_diff_and_merge_base(self):
        results=[subprocess.CompletedProcess([],0,b'c'*40+b'\n'),
                 subprocess.CompletedProcess([],0,b'M\0news/analysis_provider.py\0M\0VERSION\0')]
        with patch('ci.browser_selection.subprocess.run',side_effect=results) as run:
            self.assertFalse(select(changed_files('a'*40,'b'*40))[0])
            self.assertEqual(run.call_args.args[0][-3:],['c'*40,'b'*40,'--'])
        with patch('ci.browser_selection.subprocess.run',side_effect=[results[0],subprocess.CompletedProcess([],0,b'M\0broken')]):
            self.assertTrue(decision('pull_request','a'*40,'b'*40)[0])

    def test_outputs_and_summary_are_written_for_both_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'output';summary=Path(directory)/'summary'
            with patch.dict('os.environ',{'GITHUB_OUTPUT':str(output),'GITHUB_STEP_SUMMARY':str(summary)}):
                for run in [True,False]:
                    with patch('ci.browser_selection.decision',return_value=(run,'Static reason.')):
                        main()
                    self.assertIn(f'run_browsers={str(run).lower()}',output.read_text())
                    self.assertIn('Static reason.',summary.read_text())
