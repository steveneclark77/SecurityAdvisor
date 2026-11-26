"""Exercise isolated provider boundaries without live credentials or network calls."""
import io
import json
import runpy
import urllib.error
from unittest.mock import Mock,patch
from django.test import SimpleTestCase,override_settings
from . import analysis_provider as ap, slack_transport as st,feed_transport as ft
from .openai_tests import test_connection
from django.core.management.base import CommandError


def response(raw):
    result=Mock();result.__enter__=Mock(return_value=result);result.__exit__=Mock(return_value=False)
    result.read.return_value=raw
    return result


def entry(module,payload,fail=False):
    stdin=io.StringIO(json.dumps(payload));stdin.buffer=io.BytesIO(json.dumps(payload).encode())
    stdout=io.StringIO();stdout.buffer=io.BytesIO();stderr=io.StringIO()
    with patch('sys.stdin',stdin),patch('sys.stdout',stdout),patch('sys.stderr',stderr):
        if fail:
            try:
                runpy.run_module(module,run_name='__main__')
            except SystemExit as exc:
                assert exc.code==1
            else:
                raise AssertionError('Expected unsuccessful exit')
        else:
            runpy.run_module(module,run_name='__main__')
    return stdout.getvalue(),stderr.getvalue(),stdout.buffer.getvalue()


class ProviderBoundaryTests(SimpleTestCase):
    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic'})
    def test_openai_transport_validates_operation_key_size_and_redirects(self):
        with self.assertRaises(ValueError): ap.post_json('/unknown',{})
        with patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':''}),self.assertRaises(ValueError): ap.post_json('/embeddings',{})
        with self.assertRaises(ValueError): ap.NoRedirect().redirect_request()
        with patch.object(ap.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=response(b'{"ok":true}')
            self.assertEqual(ap.post_json('/embeddings',{'input':'synthetic'}),{'ok':True})
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://api.openai.com/v1/embeddings')
            self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'],30)
            opener.return_value.open.return_value=response(b'x'*(ap.MAX_RESPONSE+1))
            with self.assertRaises(ValueError): ap.post_json('/embeddings',{})
        good={'choices':[{'finish_reason':'stop','message':{'content':'{"issues":[]}'}}],'usage':{'prompt_tokens':1}}
        with patch.object(ap,'post_json',return_value=good):
            self.assertEqual(ap.request_analysis({})['output'],{'issues':[]})
        for choice in [{'finish_reason':'length','message':{}},{'finish_reason':'stop','message':{'refusal':'No'}}]:
            with patch.object(ap,'post_json',return_value={'choices':[choice]}),self.assertRaises(ValueError): ap.request_analysis({})

    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic'})
    def test_analysis_subprocess_entry_success_and_safe_failure(self):
        good={'choices':[{'finish_reason':'stop','message':{'content':'{"issues":[]}'}}],'usage':{}}
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response(json.dumps(good).encode())
            self.assertEqual(json.loads(entry('news.analysis_provider',{})[0])['output'],{'issues':[]})
            opener.return_value.open.side_effect=ValueError('synthetic-secret')
            out,err,_=entry('news.analysis_provider',{},fail=True)
            self.assertEqual(out,'');self.assertNotIn('synthetic-secret',err)

    def test_embedding_and_probe_entries(self):
        with patch.object(ap,'post_json',return_value={'data':[{'embedding':[.1]*256}],'usage':{'total_tokens':2}}):
            self.assertEqual(json.loads(entry('news.embedding_provider',{})[0])['tokens'],2)
        with patch.object(ap,'post_json',side_effect=ValueError('private')):
            self.assertNotIn('private',entry('news.embedding_provider',{},fail=True)[1])
            from .openai_probe import probe
            self.assertEqual([r['status'] for r in probe({'analysis':'a','embeddings':'b'})],['request_failed']*2)
            self.assertEqual(len(json.loads(entry('news.openai_probe',{'analysis':'a','embeddings':'b'})[0])),2)
        entry('news.openai_probe',{},fail=True)

    @override_settings(NEWS_ANALYSIS_MODEL='',NEWS_EMBEDDING_MODEL='synthetic')
    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic'})
    def test_probe_command_missing_model(self):
        with self.assertRaisesMessage(CommandError,'both'): test_connection()

    @patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic'})
    def test_probe_command_invalid_result_and_failed_outcomes(self):
        for output in [[{'kind':'wrong'}],[{'kind':'analysis','status':'access_denied'},{'kind':'embeddings','status':'ok'}]]:
            with patch('news.openai_tests.subprocess.run',return_value=Mock(returncode=0,stdout=json.dumps(output).encode())),self.assertRaises(CommandError):
                test_connection()

    @patch.dict('os.environ',{'NEWS_SLACK_BOT_TOKEN':'synthetic'})
    def test_slack_http_failures_size_and_rate_limit(self):
        for method in ['unknown']:
            with self.assertRaises(ValueError): st.api(method,{})
        with patch.dict('os.environ',{'NEWS_SLACK_BOT_TOKEN':''}),self.assertRaises(ValueError): st.api('auth.test',{})
        with patch.object(st.urllib.request,'build_opener') as opener:
            for code,expected in [(401,'invalid_auth'),(403,'restricted_action'),(429,'rate_limited'),(500,None)]:
                opener.return_value.open.side_effect=urllib.error.HTTPError('https://slack.com',code,'private',None,None)
                with self.assertRaises(st.SlackAPIError if expected else OSError) as caught: st.api('auth.test',{})
                if expected: self.assertEqual(caught.exception.code,expected)
            opener.return_value.open.side_effect=None
            opener.return_value.open.return_value=response(b'x'*(1024*1024+1))
            with self.assertRaises(ValueError): st.api('auth.test',{})
            opener.return_value.open.return_value=response(b'{"ok":false,"error":"ratelimited"}')
            with self.assertRaises(st.SlackAPIError) as caught: st.api('auth.test',{})
            self.assertEqual(caught.exception.code,'rate_limited')
            opener.return_value.open.return_value=response(b'{"ok":true}')
            self.assertTrue(st.api('auth.test',{})['ok'])

    def test_slack_channel_pagination_rejections_and_uncertain_posts(self):
        for channel in [{'is_archived':True},{'is_member':False}]:
            with patch.object(st,'api',return_value={'channels':[{'name':'security-advisor-notifications',**channel}]}),self.assertRaises(ValueError): st.find_channel()
        with patch.object(st,'api',side_effect=[{'channels':[],'response_metadata':{'next_cursor':'next'}},{'channels':[]},{'channels':[]}]),self.assertRaises(ValueError): st.find_channel()
        with patch.object(st,'api',side_effect=OSError): self.assertEqual(st.send({})['error_code'],'connection_failed')
        for value in [{'ts':'bad'},OSError('private')]:
            with patch.object(st,'find_channel',return_value={'id':'C'}),patch.object(st,'api',side_effect=[{'url':'https://securityadvisor-talk.slack.com/'},value]):
                self.assertEqual(st.send({})['status'],'unknown')
        with patch.object(st,'api',return_value={'url':'https://wrong.slack.com'}):
            self.assertEqual(st.send({})['error_code'],'workspace_mismatch')
        with patch('urllib.request.build_opener',side_effect=OSError):
            self.assertEqual(json.loads(entry('news.slack_transport',{})[0])['status'],'failed')
        with patch('json.loads',side_effect=ValueError):
            out=entry('news.slack_transport',{})[0]
        self.assertEqual(json.loads(out)['status'],'unknown')

    @override_settings(NEWS_ALLOWED_HOSTS=['example.test'])
    def test_feed_validation_redirects_handler_and_bounds(self):
        with patch.object(ft.socket,'getaddrinfo',return_value=[]),self.assertRaises(ValueError): ft.public_address('example.test')
        with self.assertRaises(ValueError): ft.validate_url('https://unknown.test',feed=True)
        with patch.object(ft,'public_address',return_value='8.8.8.8'):
            from urllib.request import Request
            req=Request('https://example.test/')
            redirect=ft.SafeRedirect().redirect_request(req,None,302,'',{},'https://example.test/new')
            self.assertEqual(redirect.full_url,'https://example.test/new')
            with patch.object(ft.PinnedHTTPSHandler,'do_open',return_value='opened') as opened:
                self.assertEqual(ft.PinnedHTTPSHandler().https_open(req),'opened');opened.assert_called_once()
            with patch.object(ft,'build_opener') as opener:
                res=response(b'');res.read1.side_effect=[b'feed',b''];opener.return_value.open.return_value=res
                self.assertEqual(ft.fetch_feed('https://example.test'),b'feed')
                res.read1.side_effect=[b'x'*(ft.MAX_BYTES+1)]
                with self.assertRaises(ValueError): ft.fetch_feed('https://example.test')
        with patch('django.conf.LazySettings.configure'),patch.object(ft,'public_address',return_value='8.8.8.8'):
            # runpy defines its own functions: patch the network primitives they use.
            with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch('urllib.request.build_opener') as opener:
                res=response(b'');res.read1.side_effect=[b'feed',b''];opener.return_value.open.return_value=res
                payload={'allowed_hosts':['example.test'],'app_version':'synthetic','url':'https://example.test'}
                self.assertEqual(entry('news.feed_transport',payload)[2],b'feed')
                opener.return_value.open.side_effect=OSError('private')
                self.assertNotIn('private',entry('news.feed_transport',payload,fail=True)[1])
        conn=ft.PinnedHTTPSConnection('unknown.test')
        with self.assertRaises(ValueError): conn.connect()

    def test_source_url_length_limit(self):
        from .source_urls import canonical_source_url
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError): canonical_source_url('https://example.test/'+'x'*1000)
