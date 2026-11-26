"""No test sends a real Slack message or reads production credentials."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock,patch
from django.contrib.auth import get_user_model
from django.core.management import call_command,CommandError
from django.db import connection,IntegrityError,transaction
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from .models import SlackTestRequest,DigestDelivery,InboxEvent
from .slack_tests import configuration_status,deliver_test,process_test_requests
from .slack_transport import send,api,diagnostic,SlackAPIError


@override_settings(NEWS_PUBLIC_BASE_URL='https://app.example.test',NEWS_SLACK_DIGEST_ENABLED=False)
class SlackConnectionTests(TestCase):
    def setUp(self):
        self.enterContext(patch.dict('os.environ',{'NEWS_SLACK_BOT_TOKEN':'synthetic-secret-never-display'}))
        self.admin=get_user_model().objects.create_superuser('slack-admin',password='synthetic-password')

    def test_command_sends_labeled_message_without_news_or_digest_changes(self):
        output=StringIO()
        transport=Mock(return_value={'status':'sent','timestamp':'123.456'})
        with patch('news.slack_tests.transport',transport):
            call_command('test_news_slack',stdout=output)
        self.assertIn('Test message sent',output.getvalue())
        payload=transport.call_args.args[0]
        self.assertIn('Slack connection test',payload['text'])
        self.assertIn('Requested test notification',json.dumps(payload))
        self.assertIn('https://app.example.test/news/',json.dumps(payload))
        self.assertFalse(InboxEvent.objects.exists())
        self.assertFalse(DigestDelivery.objects.exists())
        self.assertEqual(SlackTestRequest.objects.get().origin,'cli')

    def test_test_message_does_not_touch_an_existing_digest_window(self):
        DigestDelivery.objects.create(day=timezone.now().date(),status='sent',first_event_id=1,last_event_id=10,payload={'text':'Preserved digest'})
        before=list(DigestDelivery.objects.values())
        with patch('news.slack_tests.transport',return_value={'status':'sent','timestamp':'123.456'}):
            call_command('test_news_slack',stdout=StringIO())
        self.assertEqual(list(DigestDelivery.objects.values()),before)

    def test_configuration_status_is_local_and_never_exposes_values(self):
        with self.assertNumQueries(0),patch('news.slack_tests.transport') as remote:
            text=configuration_status()
            self.assertIn('digest disabled',text)
            self.assertIn('token configured',text)
            self.assertNotIn('synthetic-secret',text)
            self.assertNotIn('app.example.test',text)
            remote.assert_not_called()
        for origin in ['https://user:secret@example.test/','https://app.example.test:bad','https://app.example.test:0','https://app.example.test/\nprivate']:
            with override_settings(NEWS_PUBLIC_BASE_URL=origin):
                self.assertIn('origin missing or invalid',configuration_status())

    def test_missing_settings_are_actionable_without_network(self):
        with patch.dict('os.environ',{'NEWS_SLACK_BOT_TOKEN':''}),patch('news.slack_tests.transport') as remote:
            with self.assertRaisesMessage(CommandError,'NEWS_SLACK_BOT_TOKEN'):
                call_command('test_news_slack')
            remote.assert_not_called()
        with override_settings(NEWS_PUBLIC_BASE_URL=''),patch('news.slack_tests.transport') as remote:
            with self.assertRaisesMessage(CommandError,'NEWS_PUBLIC_BASE_URL'):
                call_command('test_news_slack')
            remote.assert_not_called()

    def test_sanitized_failures_and_uncertain_delivery_exit_nonzero(self):
        for status,code,expected in [('failed','missing_scope','required scope'),('failed','invalid_auth','bot token'),
                                     ('failed','workspace_mismatch','different workspace'),('unknown','delivery_unconfirmed','Check the channel')]:
            with patch('news.slack_tests.transport',return_value={'status':status,'error_code':code,'remote_body':'synthetic-secret'}):
                with self.assertRaises(CommandError) as caught:
                    call_command('test_news_slack')
                self.assertIn(expected,str(caught.exception))
                self.assertNotIn('synthetic-secret',str(caught.exception))
        self.assertFalse(DigestDelivery.objects.exists())

    def test_delivery_is_claimed_once_and_finished_history_is_retained(self):
        request=SlackTestRequest.objects.create(origin='cli')
        transport=Mock(return_value={'status':'sent','timestamp':'123.456'})
        first=deliver_test(request.pk,call=transport)
        again=deliver_test(request.pk,call=transport)
        self.assertEqual(first.pk,again.pk)
        self.assertEqual(transport.call_count,1)
        with self.assertRaises(IntegrityError),transaction.atomic():
            SlackTestRequest.objects.filter(pk=request.pk).update(message='Overwritten')
        with self.assertRaises(IntegrityError),transaction.atomic():
            SlackTestRequest.objects.filter(pk=request.pk).delete()

    def test_untrusted_success_timestamp_is_not_retained(self):
        request=SlackTestRequest.objects.create(origin='cli')
        result=deliver_test(request.pk,call=lambda payload:{'status':'sent','timestamp':'synthetic-secret'})
        self.assertEqual(result.status,'unknown')
        self.assertEqual(result.slack_timestamp,'')
        self.assertNotIn('synthetic-secret',result.message)

    def test_notification_loop_processes_explicit_test_when_digests_disabled(self):
        request=SlackTestRequest.objects.create(actor=self.admin)
        output=StringIO()
        with patch('news.slack_tests.transport',return_value={'status':'sent','timestamp':'123.456'}),patch('news.management.commands.send_news_digest.time.sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                call_command('send_news_digest',loop=True,stdout=output)
        request.refresh_from_db()
        self.assertEqual(request.status,'sent')
        self.assertIn('Local check only; no message sent.',output.getvalue())
        self.assertFalse(DigestDelivery.objects.exists())

    def test_worker_does_not_steal_a_direct_cli_request(self):
        request=SlackTestRequest.objects.create(origin='cli')
        with patch('news.slack_tests.transport') as transport:
            self.assertEqual(process_test_requests(),[])
            transport.assert_not_called()
        request.refresh_from_db()
        self.assertEqual(request.status,'pending')
        self.assertEqual(deliver_test(request.pk,call=lambda payload:{'status':'sent','timestamp':'123.456'}).status,'sent')

    def test_interrupted_test_becomes_unknown_without_retry(self):
        request=SlackTestRequest.objects.create(origin='cli',status='sending',started_at=timezone.now()-timedelta(minutes=6))
        with patch('news.slack_tests.transport') as transport:
            self.assertEqual(process_test_requests(),[])
            transport.assert_not_called()
        request.refresh_from_db()
        self.assertEqual(request.status,'unknown')

    def test_admin_queue_requires_confirmation_csrf_and_superuser(self):
        path=reverse('admin:news_slacktestrequest_add')
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.get(path).status_code,200)
        csrf=client.cookies['csrftoken'].value
        self.assertEqual(client.post(path,{'confirm':'on'}).status_code,403)
        self.assertEqual(client.post(path,{'confirm':'on','csrfmiddlewaretoken':csrf},HTTP_ORIGIN='https://foreign.test').status_code,403)
        self.assertEqual(client.post(path,{'csrfmiddlewaretoken':csrf},HTTP_ORIGIN='http://testserver').status_code,200)
        self.assertFalse(SlackTestRequest.objects.exists())
        with patch('news.slack_tests.transport') as transport:
            self.assertEqual(client.post(path,{'confirm':'on','csrfmiddlewaretoken':csrf},HTTP_ORIGIN='http://testserver').status_code,302)
            transport.assert_not_called()
        self.assertEqual(SlackTestRequest.objects.get().actor,self.admin)
        user=get_user_model().objects.create_user('slack-staff',is_staff=True)
        client.force_login(user)
        self.assertEqual(client.get(path).status_code,403)
        self.assertEqual(client.post(path,{'confirm':'on','csrfmiddlewaretoken':csrf},HTTP_ORIGIN='http://testserver').status_code,403)

    def test_public_channel_does_not_need_private_read_scope(self):
        with patch('news.slack_transport.api',side_effect=[{'url':'https://securityadvisor-talk.slack.com/'},
            {'channels':[{'name':'security-advisor-notifications','id':'C-SYNTHETIC','is_member':True}]},{'ts':'123.456'}]) as request:
            self.assertEqual(send({'text':'Synthetic test'})['status'],'sent')
            self.assertEqual(request.call_args_list[1].args[1]['types'],'public_channel')
            self.assertEqual(request.call_count,3)

    def test_private_channel_lookup_and_explicit_post_errors(self):
        with patch('news.slack_transport.api',side_effect=[{'url':'https://securityadvisor-talk.slack.com/'},
            {'channels':[]},{'channels':[{'name':'security-advisor-notifications','id':'G-SYNTHETIC','is_member':True}]},
            SlackAPIError('not_in_channel')]) as request:
            result=send({'text':'Synthetic test'})
            self.assertEqual(result,{'status':'failed','error_code':'not_in_channel'})
            self.assertEqual(request.call_args_list[2].args[1]['types'],'private_channel')
            self.assertIn('Invite the bot',diagnostic(result))

    def test_unknown_remote_error_text_is_not_saved_or_returned(self):
        response=Mock()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({'ok':False,'error':'synthetic-secret-token'}).encode()
        with patch('news.slack_transport.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=response
            with self.assertRaises(ValueError) as caught:
                api('auth.test',{})
            self.assertNotIn('synthetic-secret',str(caught.exception))

    def test_ambiguous_post_error_requires_checking_channel_before_retry(self):
        with patch('news.slack_transport.api',side_effect=[{'url':'https://securityadvisor-talk.slack.com/'},
            {'channels':[{'name':'security-advisor-notifications','id':'C-SYNTHETIC','is_member':True}]},
            SlackAPIError('internal_error')]):
            self.assertEqual(send({'text':'Synthetic test'}),{'status':'unknown','error_code':'delivery_unconfirmed'})

    def test_workspace_check_rejects_old_url_and_hostname_lookalikes_before_posting(self):
        for url in ['https://securityadvisor.slack.com/',
                    'https://securityadvisor-talk.slack.com.attacker.test/',
                    'https://attacker.test/securityadvisor-talk.slack.com/',
                    'https://securityadvisor-talk.slack.com@attacker.test/']:
            with self.subTest(url=url),patch('news.slack_transport.api',return_value={'url':url}) as api:
                self.assertEqual(send({'text':'Synthetic test'}),{'status':'failed','error_code':'workspace_mismatch'})
                self.assertEqual(api.call_count,1)
