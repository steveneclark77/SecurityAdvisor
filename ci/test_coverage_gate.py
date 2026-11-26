import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from .coverage_gate import failures,main


def report(lines=9,statements=10,branches=0,total_branches=0):
    return {'meta':{'branch_coverage':True},'files':{'module.py':{'summary':{
        'covered_lines':lines,'num_statements':statements,'covered_branches':branches,'num_branches':total_branches}}}}


class CoverageGateTests(TestCase):
    def test_exact_threshold_branch_counts_and_empty_modules(self):
        self.assertEqual(failures(report()),[])
        self.assertEqual(failures(report(0,0)),[])
        self.assertEqual(len(failures(report(9,10,0,2))),1)
        self.assertEqual(len(failures(report(89999,100000))),1)
        self.assertEqual(failures(report(9,10,9,10)),[])

    def test_high_average_cannot_hide_low_module(self):
        data=report(10000,10000);data['files']['low.py']=report(8,10)['files']['module.py']
        self.assertEqual(failures(data),[('low.py',80.0)])

    def test_missing_invalid_and_line_only_reports_fail(self):
        for data in [{},{'meta':{'branch_coverage':True},'files':{}},report(-1),report(11),report(True),
                     {**report(),'meta':{'branch_coverage':False}}]:
            with self.assertRaises((ValueError,KeyError,TypeError)): failures(data)
        with patch('sys.argv',['coverage_gate','/missing/coverage.json']): self.assertEqual(main(),1)

    def test_command_status_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'coverage.json';summary=Path(directory)/'summary'
            for value,expected in [(report(),0),(report(8,10),1)]:
                path.write_text(json.dumps(value))
                with patch('sys.argv',['coverage_gate',str(path)]),patch.dict('os.environ',{'GITHUB_STEP_SUMMARY':str(summary)}):
                    self.assertEqual(main(),expected)
            self.assertIn('FAIL: 1 module',summary.read_text())
