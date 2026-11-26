"""Synthetic matching/calibration/notification checks; no live external messages."""
import copy
from datetime import datetime,timezone as tz,timedelta
from io import StringIO
from unittest.mock import patch,Mock
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management import call_command
from django.db import connection,IntegrityError,transaction
from django.test import TestCase,override_settings
from django.urls import reverse
from .access import REVIEWER_GROUP
from .models import (Issue,IssueProposal,AnalysisResult,MatchAssessment,MatchDecision,MatchFeedback,
    MatchingConfiguration,CalibrationVersion,InboxReceipt,EmbeddingCache,MatchComparison,InboxEvent,DigestDelivery)
from .match_cache import refresh_profile,get_embedding,extraction_data,summary,DIMENSIONS
from .matching import assess,prepare_cache,MATCH_POLICY,process_pending
from .match_review import act,apply_automatic
from .calibration import build_calibration,configure
from .versioning import create_version
from .digest import send_digest
from testsupport.news_matching import make_proposal


def fake_embedding(text):
    return {'vector':[1.0]+[0.0]*(DIMENSIONS-1),'tokens':10}


class MatchingTests(TestCase):
    def setUp(self):
        self.enterContext(patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-key','NEWS_SLACK_BOT_TOKEN':'synthetic-bot'}))
        self.user=get_user_model().objects.create_superuser('matching-admin',password='synthetic-password')
        with patch('django.utils.timezone.now',return_value=datetime(2026,1,1,tzinfo=tz.utc)):
            self.f=make_proposal(self.user)

    def issue(self):
        issue=Issue.objects.create(source=self.f.source,first_scan=self.f.article.first_scan,identity='synthetic-issue',last_seen_at=self.f.article.last_seen_at)
        create_version(issue=issue,expected_version_id=None,content={**self.f.proposal.content,'url':self.f.article.url},actor=self.user,change_reason='Synthetic fixture')
        refresh_profile(issue.pk,products=['Synthetic product'],versions=['1.0'])
        issue.refresh_from_db()
        return issue

    def prepared(self):
        prepare_cache([self.f.proposal],call=fake_embedding)
        return assess(self.f.proposal)

    def activate(self,assessment):
        calibration=CalibrationVersion.objects.create(name='Synthetic evaluated fixture',policy_version=MATCH_POLICY,dataset_hash='synthetic',label_ids=[],
            metrics={'embedding_model':settings.NEWS_EMBEDDING_MODEL,'buckets':{assessment.bucket:{'confidence':.96,'eligible':True,'train_n':100,'heldout_n':100}}},created_by=self.user)
        configure(actor=self.user,calibration=calibration,autonomous=True)
        return assess(self.f.proposal)

    def test_learning_mode_and_default_off_workers(self):
        self.issue()
        assessment=self.prepared()
        self.assertEqual(assessment.prediction,'match')
        self.assertIsNone(apply_automatic(assessment))
        self.assertFalse(MatchDecision.objects.exists())
        for command in ['match_news','send_news_digest']:
            with override_settings(NEWS_ANALYSIS_ENABLED=False,NEWS_SLACK_DIGEST_ENABLED=False),self.assertNumQueries(2 if command=='send_news_digest' else 0),patch(f'news.management.commands.{command}.time.sleep',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    call_command(command,loop=True,stdout=StringIO())

    def test_accepted_content_review_adds_identity_label_but_rejection_does_not(self):
        from .analysis import decide_proposal
        decision=decide_proposal(proposal=self.f.proposal,actor=self.user,decision='accept',rationale='Human confirmed a new incident')
        self.assertEqual(MatchFeedback.objects.get().correct_issue_id,decision.issue_version.issue_id)
        second=make_proposal(self.user)
        decide_proposal(proposal=second.proposal,actor=self.user,decision='reject',rationale='Unsupported remediation, not an identity judgment')
        self.assertFalse(MatchFeedback.objects.filter(proposal=second.proposal).exists())

    def test_embedding_comparison_and_severity_only_cache_reuse(self):
        issue=self.issue()
        provider=Mock(side_effect=fake_embedding)
        prepare_cache([self.f.proposal],call=provider)
        first=assess(self.f.proposal)
        count=provider.call_count
        comparison_count=MatchComparison.objects.count()
        again=assess(self.f.proposal)
        self.assertEqual(first.pk,again.pk)
        self.assertEqual(MatchComparison.objects.count(),comparison_count)
        previous=issue.match_profile.identity_hash
        create_version(issue=issue,expected_version_id=issue.current_version_id,content={'severity':'high','remediation':'Changed recommendation'},actor=self.user,change_reason='Severity-only change')
        prepare_cache([self.f.proposal],call=provider)
        self.assertEqual(provider.call_count,count)
        issue.refresh_from_db()
        self.assertEqual(issue.match_profile.identity_hash,previous)
        self.assertTrue(EmbeddingCache.objects.exists())

    def test_derived_index_keys_do_not_reject_valid_long_issue_fields(self):
        issue=self.issue()
        version=create_version(issue=issue,expected_version_id=issue.current_version_id,
            content={'name':'X'*500,'identifiers':'CVE-2026-'+'9'*1000},actor=self.user,change_reason='Synthetic long-field boundary')
        profile=refresh_profile(issue.pk)
        self.assertTrue(all(len(key.value)<=200 for key in profile.keys.all()))
        self.assertEqual(version.name,'X'*500)
        self.assertEqual(len(version.identifiers),1009)

    def test_embedding_model_change_invalidates_coverage_and_old_confidence(self):
        self.issue()
        original=self.activate(self.prepared())
        self.assertIsNotNone(original.confidence)
        with override_settings(NEWS_EMBEDDING_MODEL='synthetic-embedding-v2'):
            incomplete=assess(self.f.proposal)
            self.assertFalse(incomplete.evidence['complete'])
            self.assertIsNone(incomplete.confidence)
            self.assertIsNone(apply_automatic(original))
            prepare_cache([self.f.proposal],call=fake_embedding)
            refreshed=assess(self.f.proposal)
            self.assertTrue(refreshed.evidence['complete'])
            self.assertIsNone(refreshed.confidence)

    def test_below_threshold_and_tied_candidates_need_human_review(self):
        issue=self.issue()
        assessment=self.prepared()
        calibration=CalibrationVersion.objects.create(name='Synthetic below-threshold fixture',policy_version=MATCH_POLICY,dataset_hash='synthetic',label_ids=[],
            metrics={'embedding_model':settings.NEWS_EMBEDDING_MODEL,'buckets':{assessment.bucket:{'confidence':.899,'eligible':True}}},created_by=self.user)
        configure(actor=self.user,calibration=calibration,autonomous=True)
        self.assertIsNone(apply_automatic(assess(self.f.proposal)))
        other=Issue.objects.create(source=self.f.source,first_scan=self.f.article.first_scan,identity='second-similar-incident',last_seen_at=issue.last_seen_at)
        create_version(issue=other,expected_version_id=None,content={**self.f.proposal.content,'url':self.f.article.url},actor=self.user,change_reason='Synthetic second issue')
        refresh_profile(other.pk,products=['Synthetic product'],versions=['1.0'])
        prepare_cache([self.f.proposal],call=fake_embedding)
        ambiguous=assess(self.f.proposal)
        self.assertEqual(ambiguous.prediction,'ambiguous')
        self.assertIsNone(apply_automatic(ambiguous))

    def test_autonomous_duplicate_only_links_and_is_idempotent(self):
        issue=self.issue()
        before=issue.current_version_id
        assessment=self.activate(self.prepared())
        action=apply_automatic(assessment)
        self.assertTrue(action.automatic)
        self.assertEqual(action.issue_id,issue.pk)
        issue.refresh_from_db()
        self.assertEqual(issue.current_version_id,before)
        self.assertEqual(issue.versions.count(),1)
        self.assertFalse(MatchFeedback.objects.exists())
        self.assertEqual(apply_automatic(assessment).pk,action.pk)
        self.assertEqual(InboxEvent.objects.filter(kind='automatic_link').count(),1)

    def test_autonomous_new_is_unreviewed_and_notifies(self):
        assessment=self.activate(self.prepared())
        self.assertEqual(assessment.prediction,'new')
        decision=apply_automatic(assessment)
        decision.issue.refresh_from_db()
        self.assertEqual(decision.issue.review_status(),'Needs review')
        self.assertEqual(decision.issue.current_version.origin,'automated_proposal')
        self.assertEqual(InboxEvent.objects.filter(kind='new').count(),1)

    def test_uncalibrated_incomplete_and_ambiguous_stay_human(self):
        issue=self.issue()
        incomplete=assess(self.f.proposal)
        self.assertFalse(incomplete.evidence['complete'])
        self.assertIsNone(apply_automatic(incomplete))
        self.assertFalse(MatchDecision.objects.exists())
        bad=CalibrationVersion.objects.create(name='No evidence',policy_version=MATCH_POLICY,label_ids=[],dataset_hash='none',metrics={'buckets':{}},created_by=self.user)
        with self.assertRaises(ValidationError):
            configure(actor=self.user,calibration=bad,autonomous=True)
        self.assertEqual(issue.versions.count(),1)

    def test_human_decisions_and_corrections_preserve_history(self):
        issue=self.issue()
        assessment=self.prepared()
        first=act(assessment,outcome='match',target_issue_id=issue.pk,actor=self.user,rationale='Confirmed same incident')
        with self.assertRaises(ValidationError):
            act(assessment,outcome='irrelevant',actor=self.user,rationale='Stale correction')
        second=act(assessment,outcome='irrelevant',actor=self.user,rationale='Corrected classification',expected_decision_id=first.pk)
        self.assertEqual(MatchFeedback.objects.count(),2)
        self.assertEqual(second.outcome,'irrelevant')
        self.assertTrue(issue.article_links.filter(relationship='retracts').exists())
        self.assertEqual(issue.versions.count(),1)
        for record in [assessment,first,MatchFeedback.objects.first(),self.f.event]:
            with self.assertRaises(ValidationError): record.save()
            with self.assertRaises(IntegrityError),transaction.atomic(),connection.cursor() as cursor:
                cursor.execute('DELETE FROM '+connection.ops.quote_name(record._meta.db_table)+' WHERE id=%s',[record.pk])

    def test_reviewer_group_required_even_for_superusers(self):
        stranger=get_user_model().objects.create_superuser('non-reviewing-admin',password='synthetic-password')
        self.client.force_login(stranger)
        for url in [reverse('news_inbox'),reverse('news_match_review',args=[self.f.proposal.pk])]:
            self.assertEqual(self.client.get(url).status_code,403)
        with self.assertRaises(PermissionDenied):
            act(self.f.assessment,outcome='irrelevant',actor=stranger,rationale='Not a member')
        staff=get_user_model().objects.create_user('reviewing-staff',is_staff=True)
        staff.groups.add(Group.objects.get(name=REVIEWER_GROUP))
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/news/matchingconfiguration/1/change/').status_code,403)
        with self.assertRaises(PermissionDenied):
            configure(actor=staff,calibration=None,autonomous=False)

    def test_inbox_read_is_personal_and_post_only(self):
        self.client.force_login(self.user)
        url=reverse('news_inbox_read')
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url,{'event':self.f.event.pk}).status_code,302)
        self.assertTrue(InboxReceipt.objects.filter(user=self.user,event=self.f.event).exists())
        response=self.client.get(reverse('news_inbox'))
        self.assertNotContains(response,self.f.proposal.content['name'])

    def test_failed_embedding_attempts_are_bounded_and_reserved(self):
        failed=Mock(side_effect=RuntimeError('synthetic-secret'))
        for _ in range(settings.NEWS_ANALYSIS_MAX_ATTEMPTS+2):
            self.assertIsNone(get_embedding('Synthetic failed input',prepare=True,call=failed))
        self.assertEqual(failed.call_count,settings.NEWS_ANALYSIS_MAX_ATTEMPTS)
        from .models import EmbeddingAttempt,AnalysisBudget
        self.assertNotIn('synthetic-secret',EmbeddingAttempt.objects.first().error)
        self.assertEqual(AnalysisBudget.objects.get().reserved_cents,settings.NEWS_EMBEDDING_PER_RUN_CENTS*settings.NEWS_ANALYSIS_MAX_ATTEMPTS)

    def test_work_queue_rotates_past_unprepared_records(self):
        from .models import MatchQueue
        more=[make_proposal() for _ in range(3)]
        for _ in range(4): process_pending(limit=1)
        self.assertEqual(MatchQueue.objects.filter(last_processed_at__isnull=False).count(),4)
        self.assertEqual(len(more),3)

    @override_settings(NEWS_SLACK_DIGEST_ENABLED=True,NEWS_PUBLIC_BASE_URL='https://app.example.test')
    def test_daily_slack_schedule_empty_behavior_and_links_only(self):
        before=datetime(2027,1,1,16,59,tzinfo=tz.utc)
        now=datetime(2027,1,1,17,0,tzinfo=tz.utc)
        send=Mock(return_value={'status':'sent','timestamp':'123.456'})
        self.assertIsNone(send_digest(now=before,call=send))
        delivery=send_digest(now=now,call=send)
        self.assertEqual(delivery.status,'sent')
        self.assertNotIn('csrf-news.test',str(delivery.payload))
        self.assertIn('https://app.example.test/news/',str(delivery.payload))
        self.assertEqual(send_digest(now=now,call=send).pk,delivery.pk)
        empty=send_digest(now=now+timedelta(days=1),call=send)
        self.assertEqual(empty.status,'skipped')
        self.assertEqual(send.call_count,1)

    @override_settings(NEWS_SLACK_DIGEST_ENABLED=True,NEWS_PUBLIC_BASE_URL='https://app.example.test')
    def test_uncertain_slack_post_is_not_blindly_retried(self):
        now=datetime(2027,1,1,17,tzinfo=tz.utc)
        send=Mock(return_value={'status':'unknown'})
        delivery=send_digest(now=now,call=send)
        with self.assertRaises(ValidationError): send_digest(now=now+timedelta(days=1),call=send)
        self.assertEqual(send.call_count,1)
        call_command('send_news_digest',confirm_not_sent=delivery.pk,stdout=StringIO())
        self.assertEqual(DigestDelivery.objects.get().status,'failed')

    def test_slack_transport_checks_workspace_and_channel_before_post(self):
        from .slack_transport import send
        with patch('news.slack_transport.api',side_effect=[{'url':'https://wrong.slack.com/'}]) as api:
            self.assertEqual(send({})['status'],'failed')
            self.assertEqual(api.call_count,1)
        with patch('news.slack_transport.api',side_effect=[{'url':'https://securityadvisor.slack.com/'},
                {'channels':[{'name':'security-advisor-notifications','id':'C-SYNTHETIC'}]}, {'ts':'123.456'}]) as api:
            self.assertEqual(send({'blocks':[]})['status'],'sent')
            self.assertEqual(api.call_args.args[1]['channel'],'C-SYNTHETIC')

    def test_calibration_uses_heldout_unique_incidents_and_never_self_enables(self):
        # Bulk synthetic labels bypass work signals to keep this statistical test bounded.
        proposals=IssueProposal.objects.bulk_create([IssueProposal(result=self.f.proposal.result,position=index+1,
            content={'name':f'Independent incident {index}'},matching={}) for index in range(180)])
        issues=Issue.objects.bulk_create([Issue(source=self.f.source,first_scan=self.f.article.first_scan,
            identity=f'family-{index}',last_seen_at=self.f.article.last_seen_at) for index in range(180)])
        bucket='new|exact=0|sim=0|margin=0|ids=True|products=True|complete=True'
        for proposal,issue in zip(proposals,issues,strict=True):
            assessment=MatchAssessment.objects.create(key=f'training-{proposal.pk}',proposal=proposal,catalog_generation=0,prediction='new',
                bucket=bucket,evidence={'policy':MATCH_POLICY,'embedding_model':settings.NEWS_EMBEDDING_MODEL,'complete':True})
            decision=MatchDecision.objects.create(proposal=proposal,assessment=assessment,outcome='new',issue=issue,actor=self.user,rationale='Human-confirmed distinct incident')
            MatchFeedback.objects.create(proposal=proposal,assessment=assessment,decision=decision,outcome='new',correct_issue=issue,actor=self.user,rationale='Synthetic label')
        calibration=build_calibration('Synthetic incident evaluation',self.user)
        metrics=calibration.metrics['buckets'][bucket]
        self.assertTrue(metrics['eligible'])
        self.assertGreaterEqual(metrics['heldout_n'],30)
        self.assertGreaterEqual(metrics['train_n'],30)
        self.assertGreaterEqual(metrics['confidence'],.90)
        self.assertFalse(MatchingConfiguration.objects.get().autonomous_enabled)
        configure(actor=self.user,calibration=calibration,autonomous=True)
        # A correction to a consumed example pauses autonomy without deleting the old label.
        prior=proposals[0].match_decisions.get()
        act(prior.assessment,outcome='irrelevant',actor=self.user,rationale='Corrected ground truth',expected_decision_id=prior.pk)
        self.assertFalse(MatchingConfiguration.objects.get().autonomous_enabled)
        with self.assertRaises(ValidationError): configure(actor=self.user,calibration=calibration,autonomous=True)
        corrected=build_calibration('Corrected evaluation',self.user).metrics['buckets'][bucket]
        self.assertEqual(corrected['train_correct']+corrected['heldout_correct'],179)


from unittest import skipUnless
from django.test import TransactionTestCase


@skipUnless(connection.vendor=='postgresql','Matching locks require PostgreSQL; exercised in CI.')
class MatchingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.enterContext(patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-key'}))
        self.user=get_user_model().objects.create_superuser('concurrent-matching',password='synthetic-password')
        self.f=make_proposal(self.user)

    def test_two_workers_create_one_incident_and_notification(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections,connections
        prepare_cache([self.f.proposal],call=fake_embedding)
        assessment=assess(self.f.proposal)
        calibration=CalibrationVersion.objects.create(name='Synthetic concurrency fixture',policy_version=MATCH_POLICY,label_ids=[],dataset_hash='synthetic',
            metrics={'embedding_model':settings.NEWS_EMBEDDING_MODEL,'buckets':{assessment.bucket:{'confidence':.96,'eligible':True}}},created_by=self.user)
        configure(actor=self.user,calibration=calibration,autonomous=True)
        assessment=assess(self.f.proposal)
        barrier=Barrier(2)
        def work(_):
            close_old_connections()
            try:
                current=MatchAssessment.objects.get(pk=assessment.pk)
                barrier.wait(timeout=15)
                return apply_automatic(current).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(work,[1,2]))
        self.assertEqual(results[0],results[1])
        self.assertEqual(Issue.objects.count(),1)
        self.assertEqual(MatchDecision.objects.count(),1)
        self.assertEqual(InboxEvent.objects.filter(kind='new').count(),1)
        self.assertFalse(MatchFeedback.objects.exists())

    def test_concurrent_embedding_requests_make_one_provider_call(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections,connections
        entered=Event();release=Event();calls=[]
        def provider(text):
            calls.append(text);entered.set()
            if not release.wait(timeout=15):
                raise RuntimeError('Synthetic provider synchronization timed out')
            return fake_embedding(text)
        def work():
            close_old_connections()
            try:
                result=get_embedding('Concurrent synthetic public text',prepare=True,call=provider)
                return result.pk if result else None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(work)
            self.assertTrue(entered.wait(timeout=15))
            second=pool.submit(work)
            self.assertIsNone(second.result(timeout=15))
            release.set()
            self.assertIsNotNone(first.result(timeout=15))
        self.assertEqual(len(calls),1)
