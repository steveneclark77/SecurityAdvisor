"""Synthetic regression cases for rejected, stale and operator-driven workflows."""
import copy
import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock,patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management import call_command,CommandError
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_analysis as analysis_fixtures
from .test_analysis import output
from . import test_matching as matching_fixtures
from .test_matching import fake_embedding
from . import analysis,match_cache,calibration,matching
from .models import (AnalysisRun,AnalysisBudget,Issue,IssueArticleLink,MatchDecision,MatchingConfiguration,
                     EmbeddingAttempt,CalibrationVersion,InboxEvent,InboxReceipt,ProposalDecision)
from .forms import MatchReviewForm,review_state,sign_review
from .match_review import act
from .access import REVIEWER_GROUP


class AnalysisBoundaryTests(TestCase):
    setUp=analysis_fixtures.AnalysisTests.setUp
    analyze=analysis_fixtures.AnalysisTests.analyze
    accept=analysis_fixtures.AnalysisTests.accept

    def test_schema_limits_types_and_provider_boundary(self):
        for value,schema in [(None,analysis.string()),([1,2],analysis.array({'type':'integer'},1)),(-1,{'type':'integer','minimum':0,'maximum':0})]:
            with self.assertRaises(ValidationError): analysis.validate_schema(value,schema)
        with patch('news.analysis.subprocess.run',return_value=Mock(returncode=0,stdout=b'{"output":{}}')):
            self.assertEqual(analysis.provider({}),{'output':{}})
        with patch('news.analysis.subprocess.run',return_value=Mock(returncode=1,stdout=b'private')),self.assertRaises(ValidationError): analysis.provider({})

    def test_claim_policy_credentials_size_and_processing_idempotency(self):
        pk=analysis.queue_articles([self.article.pk])[0]
        for options in [{'NEWS_ANALYSIS_MODEL':'changed'},{'NEWS_ANALYSIS_MAX_INPUT_BYTES':1}]:
            with override_settings(**options),self.assertRaises(ValidationError): analysis.claim(pk)
        with patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':''}),self.assertRaises(ValidationError): analysis.claim(pk)
        run=analysis.process_run(pk,call=lambda payload:output())
        self.assertEqual(run.status,'succeeded');self.assertIsNone(analysis.process_run(pk))

    def test_analysis_rejects_missing_support_and_invalid_usage(self):
        mutations=[lambda r:r['usage'].update(prompt_tokens=-1),
            lambda r:r['output']['issues'][0].update(name=' '),
            lambda r:r['output']['issues'][0].update(severity_basis='unknown'),
            lambda r:r['output']['issues'][0].update(remediation_basis='unknown'),
            lambda r:r['output']['issues'][0].update(identifiers=['CVE-2026-99999']),
            lambda r:r['output']['issues'][0].update(citations=[c for c in r['output']['issues'][0]['citations'] if c['field']!='identifiers'])]
        for i,mutation in enumerate(mutations):
            result=output();mutation(result)
            with override_settings(NEWS_ANALYSIS_MODEL=f'synthetic-model-{i}'):
                self.assertEqual(self.analyze(result).status,'failed')
        self.assertFalse(ProposalDecision.objects.exists())

    def test_content_decision_rejects_invalid_and_extra_fields(self):
        proposal=self.analyze().result.proposals.get()
        for kwargs in [{'decision':'bad','rationale':'x'},{'decision':'accept','rationale':' '},
                       {'decision':'accept','rationale':'x','content':{'unexpected':'x'}}]:
            with self.assertRaises(ValidationError): analysis.decide_proposal(proposal=proposal,actor=self.user,**kwargs)
        self.assertFalse(Issue.objects.exists())

    def test_analysis_command_validation_processing_and_loop_errors(self):
        for kwargs in [{'max_records':0,'all_unanalyzed':True},{'loop':True,'article':[self.article.pk]},{}]:
            with self.assertRaises(CommandError): call_command('analyze_news',**kwargs,stdout=StringIO())
        with patch('news.management.commands.analyze_news.process_run',return_value=SimpleNamespace(pk=1,status='succeeded')):
            call_command('analyze_news',article=[self.article.pk],stdout=StringIO())
        with patch('news.management.commands.analyze_news.process_run',side_effect=ValidationError('Synthetic failure')):
            with self.assertRaises(CommandError): call_command('analyze_news',queued=True,stdout=StringIO())
            with override_settings(NEWS_ANALYSIS_ENABLED=True),patch('news.management.commands.analyze_news.time.sleep',side_effect=[None,KeyboardInterrupt]),patch('news.management.commands.analyze_news.close_old_connections'):
                with self.assertRaises(KeyboardInterrupt): call_command('analyze_news',loop=True,stdout=StringIO(),stderr=StringIO())


class MatchingBoundaryTests(TestCase):
    setUp=matching_fixtures.MatchingTests.setUp
    issue=matching_fixtures.MatchingTests.issue
    prepared=matching_fixtures.MatchingTests.prepared
    activate=matching_fixtures.MatchingTests.activate

    def test_embedding_input_prices_active_attempts_and_bad_provider_data(self):
        self.issue()
        for text,options in [('x'*40001,{}),('price',{'NEWS_EMBEDDING_INPUT_PRICE':'bad'}),
            ('negative',{'NEWS_EMBEDDING_INPUT_PRICE':'-1'}),('reservation',{'NEWS_EMBEDDING_PER_RUN_CENTS':0})]:
            with override_settings(**options),self.assertRaises(ValidationError): match_cache.get_embedding(text,prepare=True,call=fake_embedding)
        with patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':''}),self.assertRaises(ValidationError): match_cache.get_embedding('key',prepare=True)
        for i,result in enumerate([{'vector':[]},{'vector':[0.0]*256},{'vector':[1.0]*256,'tokens':-1}]):
            self.assertIsNone(match_cache.get_embedding(f'bad {i}',prepare=True,call=lambda text:result))
        key=match_cache.embedding_key('active')
        EmbeddingAttempt.objects.create(key=key,model=settings.NEWS_EMBEDDING_MODEL,content_hash='synthetic',reserved_cents=1)
        self.assertIsNone(match_cache.get_embedding('active',prepare=True))
        with override_settings(NEWS_ANALYSIS_MAX_ATTEMPTS=0): self.assertIsNone(match_cache.get_embedding('limit',prepare=True))
        with override_settings(NEWS_ANALYSIS_DAILY_CENTS=1):
            with self.assertRaises(ValidationError): match_cache.get_embedding('budget',prepare=True)
        with patch('news.match_cache.subprocess.run',return_value=Mock(returncode=0,stdout=b'{"vector":[]}')):
            self.assertEqual(match_cache.embedding_provider('text'),{'vector':[]})
        with patch('news.match_cache.subprocess.run',return_value=Mock(returncode=1,stdout=b'')),self.assertRaises(ValidationError): match_cache.embedding_provider('text')

    def test_unversioned_profile_and_rejected_match_actions(self):
        empty=Issue.objects.create(source=self.f.source,first_scan=self.f.article.first_scan,identity='empty',last_seen_at=self.f.article.last_seen_at)
        self.assertIsNone(match_cache.refresh_profile(empty.pk))
        assessment=self.prepared()
        for options in [{'outcome':'bad','rationale':'x'},{'outcome':'match','rationale':'x'},
                        {'outcome':'new','rationale':'x','content':{'unexpected':1}}]:
            with self.assertRaises(ValidationError): act(assessment,actor=self.user,**options)
        user=get_user_model().objects.create_user('limited-reviewer')
        user.groups.add(Group.objects.get_or_create(name=REVIEWER_GROUP)[0])
        with patch.object(user,'has_perms',return_value=False),self.assertRaises(PermissionDenied): act(assessment,outcome='new',actor=user,rationale='x')
        issue=self.issue()
        with self.assertRaises(ValidationError): act(assessment,outcome='match',actor=self.user,target_issue_id=issue.pk,expected_identity='stale',rationale='x')
        self.assertFalse(MatchDecision.objects.exists())

    def test_calibration_permissions_names_and_unsupported_configuration(self):
        user=get_user_model().objects.create_user('no-admin')
        with self.assertRaises(PermissionDenied): calibration.build_calibration('x',user)
        with self.assertRaises(ValidationError): calibration.build_calibration(' ',self.user)
        with self.assertRaises(PermissionDenied): calibration.configure(actor=user,calibration=None,autonomous=False)
        with self.assertRaises(ValidationError): calibration.configure(actor=self.user,calibration=None,autonomous=True)
        version=calibration.build_calibration('Synthetic empty',self.user)
        with self.assertRaises(ValidationError): calibration.configure(actor=self.user,calibration=version,autonomous=True)
        for kwargs in [{'admin':'missing','name':'x'},{'admin':self.user.username,'name':' '}]:
            with self.assertRaises(CommandError): call_command('calibrate_news',**kwargs,stdout=StringIO())
        out=StringIO();call_command('calibrate_news',admin=self.user.username,name='Command synthetic',stdout=out)
        self.assertIn('0 eligible buckets',out.getvalue())

    def test_match_worker_validates_and_handles_failure_with_full_loop(self):
        with self.assertRaises(CommandError): call_command('match_news',max_records=0)
        with patch('news.management.commands.match_news.process_pending',return_value=[]): call_command('match_news',stdout=StringIO())
        with patch('news.management.commands.match_news.process_pending',side_effect=ValidationError('synthetic')):
            with self.assertRaises(CommandError): call_command('match_news',stdout=StringIO())
            with override_settings(NEWS_ANALYSIS_ENABLED=True),patch('news.management.commands.match_news.time.sleep',side_effect=[None,KeyboardInterrupt]),patch('news.management.commands.match_news.close_old_connections'):
                with self.assertRaises(KeyboardInterrupt): call_command('match_news',loop=True,stdout=StringIO(),stderr=StringIO())

    def test_matching_forms_signed_candidates_and_invalid_decisions(self):
        issue=self.issue();assessment=self.prepared()
        proposal=self.f.proposal
        state=review_state(proposal,assessment,[issue.pk]);token=sign_review(state)
        base={'token':token,'severity':'unknown','kind':'unclassified','rationale':'Synthetic review'}
        for changes,field in [({'outcome':'match'},'target'),({'outcome':'new','name':' '},'name'),
                              ({'outcome':'uncertain','token':'bad'},'__all__'),
                              ({'outcome':'uncertain','token':sign_review({**state,'proposal':-1})},'__all__')]:
            form=MatchReviewForm({**base,**changes},proposal=proposal,assessment=assessment)
            self.assertFalse(form.is_valid());self.assertIn(field,form.errors)
        form=MatchReviewForm({**base,'outcome':'match','target':issue.pk},proposal=proposal,assessment=assessment)
        self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['expected_identity'],issue.match_profile.identity_hash)
        act(assessment,outcome='match',actor=self.user,target_issue_id=issue.pk,rationale='Link')
        self.assertEqual(review_state(proposal,assessment)['previous'],MatchDecision.objects.get().pk)

    def test_news_pages_search_empty_selection_waiting_and_issue_links(self):
        self.client.force_login(self.user)
        issue=self.issue();assessment=self.prepared()
        from .views import event_url
        pending=InboxEvent.objects.create(key='pending-synthetic',kind='pending',proposal=self.f.proposal,title='Synthetic pending')
        issue_event=InboxEvent.objects.create(key='issue-synthetic',kind='new',issue=issue,title='Synthetic new')
        other=InboxEvent.objects.create(key='other-synthetic',kind='other',title='Synthetic other')
        self.assertIn(str(issue.pk),event_url(issue_event));self.assertEqual(event_url(other),reverse('news_inbox'))
        self.assertEqual(self.client.get(reverse('news_inbox'),{'show':'all','q':'Synthetic'}).status_code,200)
        self.assertEqual(self.client.post(reverse('news_inbox_read'),{'event':['bad','99999999999999999999']}).status_code,400)
        self.assertEqual(self.client.post(reverse('news_inbox_read'),{'event':[str(pending.pk)]}).status_code,302)
        self.assertTrue(InboxReceipt.objects.filter(event=pending,user=self.user).exists())
        IssueArticleLink.objects.create(issue=issue,revision=self.f.article.current_revision,relationship='supports',actor=self.user,rationale='Synthetic')
        for query in [{},{'history':'yes','q':'Synthetic'}]:
            self.assertEqual(self.client.get(reverse('news_issue_articles',args=[issue.pk]),query).status_code,200)
        url=reverse('news_match_review',args=[self.f.proposal.pk])
        response=self.client.get(url,{'q':issue.name});self.assertEqual(response.status_code,200)
        data={**self.f.proposal.content,'token':response.context['form'].initial['token'],'outcome':'uncertain','rationale':'Need review'}
        with patch('news.views.act',side_effect=ValidationError('Synthetic stale')):
            response=self.client.post(url,data);self.assertEqual(response.status_code,200);self.assertContains(response,'Synthetic stale')
        self.assertEqual(self.client.post(url,data).status_code,302)
        from testsupport.news_matching import make_proposal
        waiting=make_proposal(self.user)
        with patch('django.db.models.query.QuerySet.first',return_value=None):
            self.assertTemplateUsed(self.client.get(reverse('news_match_review',args=[waiting.proposal.pk])),'news/review_waiting.html')

    def test_matching_cache_limits_and_weak_extraction_are_conservative(self):
        issue=self.issue()
        self.assertEqual(matching.prepare_cache([self.f.proposal],limit=1,call=fake_embedding),1)
        # A changed product extraction requires its own cache; bounded batches stop.
        self.f.proposal.matching={'affected_products':['Different synthetic product']}
        self.assertEqual(matching.prepare_cache([self.f.proposal],limit=1,call=fake_embedding),1)
        from testsupport.news_matching import make_proposal
        from .models import IssueProposal
        other=make_proposal(self.user)
        other.proposal.matching={}
        self.assertEqual(matching.assess(other.proposal).prediction,'ambiguous')
        # Missing embeddings may not be treated as evidence of an unrelated incident.
        with patch('news.matching.profile_is_current',return_value=False):
            self.assertFalse(matching.assess(self.f.proposal).evidence['complete'])
        from .analysis import decide_proposal
        decide_proposal(proposal=other.proposal,actor=self.user,decision='reject',rationale='Synthetic unrelated content')
        rows=matching.process_pending(prepare=True,call=fake_embedding)
        self.assertTrue(rows)
        other.proposal.matching_work.refresh_from_db()
        self.assertEqual(other.proposal.matching_work.status,'resolved')

    @override_settings(NEWS_PUBLIC_BASE_URL='https://app.example.test')
    def test_digest_transport_failures_and_cli_reconciliation(self):
        from .digest import transport,send_digest,ZONE
        from .models import DigestDelivery
        from django.utils import timezone
        for result,expected in [(Mock(returncode=1,stdout=b''),'unknown'),(Mock(returncode=0,stdout=b'{"status":"sent"}'),'sent')]:
            with patch('news.digest.subprocess.run',return_value=result): self.assertEqual(transport({})['status'],expected)
        with patch.dict('os.environ',{'NEWS_SLACK_BOT_TOKEN':''}),self.assertRaises(ValidationError): send_digest(force=True,call=lambda payload:{})
        from datetime import timedelta
        for offset,resolve in enumerate(['resolve_sent','confirm_not_sent'],start=1):
            row=DigestDelivery.objects.create(day=timezone.now().astimezone(ZONE).date()-timedelta(days=offset),status='unknown')
            for extra in [{'now':True},{'loop':True},{'resolve_sent':row.pk,'confirm_not_sent':row.pk}]:
                with self.assertRaises(CommandError): call_command('send_news_digest',**{resolve:row.pk,**extra},stdout=StringIO())
            call_command('send_news_digest',**{resolve:row.pk},stdout=StringIO())
            row.refresh_from_db();self.assertEqual(row.status,'sent' if resolve=='resolve_sent' else 'failed')
        with patch('news.management.commands.send_news_digest.send_digest',return_value=None):
            call_command('send_news_digest',now=True,stdout=StringIO())
        with patch('news.management.commands.send_news_digest.send_digest',side_effect=ValidationError('Synthetic preflight')):
            with self.assertRaises(CommandError): call_command('send_news_digest',now=True,stdout=StringIO())
            with override_settings(NEWS_SLACK_DIGEST_ENABLED=True),patch('news.management.commands.send_news_digest.time.sleep',side_effect=[None,KeyboardInterrupt]),patch('news.management.commands.send_news_digest.close_old_connections'):
                with self.assertRaises(KeyboardInterrupt): call_command('send_news_digest',loop=True,stdout=StringIO(),stderr=StringIO())
        row=send_digest(force=True,call=lambda payload:(_ for _ in ()).throw(OSError('private')))
        self.assertEqual(row.status,'unknown');self.assertNotIn('private',row.error)
