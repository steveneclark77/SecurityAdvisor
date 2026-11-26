import json
from io import StringIO
from unittest.mock import Mock,patch
import urllib.error
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase,override_settings
from .openai_probe import probe
from .openai_tests import configuration_status,test_connection


@override_settings(NEWS_ANALYSIS_ENABLED=False,NEWS_ANALYSIS_MODEL='synthetic-analysis',NEWS_EMBEDDING_MODEL='synthetic-embedding')
class OpenAIConnectionTests(SimpleTestCase):
    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-secret'})
    def test_local_startup_check_has_no_network_or_database_access(self):
        with patch('news.openai_tests.subprocess.run') as run:
            output=configuration_status()
            self.assertIn('automatic analysis disabled',output)
            self.assertNotIn('synthetic-secret',output)
            run.assert_not_called()
            with patch('news.management.commands.analyze_news.time.sleep',side_effect=KeyboardInterrupt):
                stdout=StringIO()
                with self.assertRaises(KeyboardInterrupt):
                    call_command('analyze_news',loop=True,stdout=stdout)
                self.assertIn('Local check only',stdout.getvalue())

    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':''})
    def test_missing_key_fails_without_calling_provider(self):
        with patch('news.openai_tests.subprocess.run') as run:
            with self.assertRaises(CommandError):
                test_connection()
            run.assert_not_called()

    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-secret'})
    def test_explicit_command_tests_both_models_without_database(self):
        result=Mock(returncode=0,stdout=json.dumps([{'kind':'analysis','status':'ok'},{'kind':'embeddings','status':'ok'}]).encode())
        with patch('news.openai_tests.subprocess.run',return_value=result) as run:
            output=StringIO();call_command('test_news_openai',stdout=output)
            self.assertIn('OpenAI embeddings: passed',output.getvalue())
            payload=json.loads(run.call_args.kwargs['input'])
            self.assertEqual(payload,{'analysis':'synthetic-analysis','embeddings':'synthetic-embedding'})
            self.assertEqual(run.call_args.kwargs['timeout'],70)

    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-secret'})
    def test_remote_errors_are_sanitized(self):
        for result in [Mock(returncode=1,stdout=b'synthetic-secret'),Mock(returncode=0,stdout=b'synthetic-secret')]:
            with patch('news.openai_tests.subprocess.run',return_value=result):
                with self.assertRaises(CommandError) as caught:
                    test_connection()
                self.assertNotIn('synthetic-secret',str(caught.exception))

    def test_probe_checks_real_response_shape_and_uses_synthetic_inputs(self):
        with patch('news.openai_probe.post_json',side_effect=[
            {'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}]},
            {'data':[{'embedding':[0.1]*256}]}]) as post:
            self.assertEqual([r['status'] for r in probe({'analysis':'a','embeddings':'b'})],['ok','ok'])
            self.assertEqual(post.call_count,2)
            self.assertEqual(post.call_args_list[0].args[0],'/chat/completions')
            self.assertEqual(post.call_args_list[1].args[0],'/embeddings')

    def test_safe_http_diagnostics_and_invalid_embedding(self):
        error=urllib.error.HTTPError('https://api.openai.com',401,'synthetic-secret',None,None)
        with patch('news.openai_probe.post_json',side_effect=[error,{'data':[{'embedding':[float('nan')]*256}]}]):
            result=probe({'analysis':'a','embeddings':'b'})
            self.assertEqual([r['status'] for r in result],['authentication_failed','invalid_response'])
            self.assertNotIn('synthetic-secret',json.dumps(result))
