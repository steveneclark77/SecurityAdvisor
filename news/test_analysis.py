"""Synthetic public-news analysis; no test contacts an AI provider or publisher."""
import copy
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .analysis import (queue_articles, process_run, decide_proposal, recover_expired, provider)
from .ingestion import scan_source
from .models import (Article, ArticleRevision, AnalysisRun, AnalysisResult, AnalysisBudget,
                     IssueProposal, ProposalDecision, Issue, IssueArticleLink, Source)
from .versioning import create_version

TEXT='CVE-2026-12345 affects Synthetic Widget 1.0. Severity is high. Upgrade to 1.1.'
RSS=('<rss><channel><item><title>Synthetic Widget advisory</title><link>https://example.test/advisory</link><description>'+TEXT+'</description></item></channel></rss>').encode()


def output():
    return {'output':{'issues':[{'name':'Synthetic Widget vulnerability','description':'Synthetic test only.',
        'severity':'high','kind':'vulnerability','remediation':'Upgrade to 1.1.', 'identifiers':['CVE-2026-12345'],
        'affected_products':['Synthetic Widget'],'affected_versions':['1.0'],
        'severity_basis':'publisher_reported','remediation_basis':'publisher_reported',
        'rationale':'The article reports an affected product and an upgrade.', 'uncertainty':'Feed excerpt only; verify vendor advice.',
        'confidence':'high','target_issue_id':0,'matching_rationale':'Match exact CVE if present.',
        'citations':[{'field':'severity','quote':'Severity is high.'},{'field':'remediation','quote':'Upgrade to 1.1.'},
                     {'field':'identifiers','quote':'CVE-2026-12345'}]}]},
        'usage':{'prompt_tokens':100,'completion_tokens':100}}


class AnalysisTests(TestCase):
    def setUp(self):
        self.enterContext(patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-not-a-real-key'}))
        self.user=get_user_model().objects.create_superuser('analysis-reviewer',password='synthetic-password')
        self.source=Source.objects.create(name='Synthetic news',url='https://example.test/',feed_url='https://example.test/rss')
        self.assertEqual(scan_source(self.source.pk,lambda url:RSS).status,'success')
        self.article=Article.objects.get(source=self.source)

    def analyze(self, response=None):
        ids=queue_articles([self.article.pk])
        return process_run(ids[0],call=lambda payload:copy.deepcopy(response or output()))

    def accept(self,proposal,**kwargs):
        return decide_proposal(proposal=proposal,actor=self.user,decision='accept',rationale='Reviewed synthetic advice',**kwargs)

    def test_capture_and_repeated_changes_do_not_publish_issues(self):
        self.assertFalse(Issue.objects.exists())
        revision=self.article.current_revision
        scan_source(self.source.pk,lambda url:RSS)
        self.assertEqual(ArticleRevision.objects.count(),1)
        scan_source(self.source.pk,lambda url:RSS.replace(b'Upgrade to 1.1.',b'Upgrade to 1.2.'))
        self.article.refresh_from_db()
        self.assertNotEqual(self.article.current_revision_id,revision.pk)
        scan_source(self.source.pk,lambda url:RSS)
        self.article.refresh_from_db()
        self.assertEqual(self.article.current_revision_id,revision.pk)
        self.assertEqual(ArticleRevision.objects.count(),2)
        self.assertFalse(Issue.objects.exists())

    def test_review_only_idempotent_queue_and_acceptance_with_user_edits(self):
        run=self.analyze()
        self.assertEqual(run.status,'succeeded')
        self.assertFalse(Issue.objects.exists())
        self.assertEqual(queue_articles([self.article.pk]),[])
        proposal=IssueProposal.objects.get()
        decision=self.accept(proposal,content={'severity':'medium','remediation':'Consultant correction'})
        self.assertEqual(decision.issue_version.severity,'medium')
        self.assertEqual(decision.issue_version.remediation,'Consultant correction')
        self.assertEqual(proposal.content['severity'],'high')
        self.assertEqual(IssueArticleLink.objects.get().revision,self.article.current_revision)
        self.assertEqual(decision.issue_version.created_by,self.user)
        self.assertEqual(decision.issue_version.references.get().source_name,'Synthetic news')
        with self.assertRaises(ValidationError):
            self.accept(proposal)

    def test_cross_publisher_exact_identifier_match_and_stale_acceptance(self):
        first=self.accept(self.analyze().result.proposals.get())
        issue=first.issue_version.issue
        other=Source.objects.create(name='Second publisher',url='https://second.test/',feed_url='https://second.test/rss')
        scan_source(other.pk,lambda url:RSS.replace(b'example.test',b'second.test'))
        article=Article.objects.get(source=other)
        run=process_run(queue_articles([article.pk])[0],call=lambda payload:output())
        proposal=run.result.proposals.get()
        self.assertEqual(proposal.target_issue_id,issue.pk)
        self.assertEqual(proposal.matching['exact_candidate_ids'],[issue.pk])
        create_version(issue=issue,expected_version_id=issue.current_version_id,content={'severity':'critical'},actor=self.user,change_reason='Concurrent consultant correction')
        with self.assertRaises(ValidationError):
            self.accept(proposal,target_issue_id=issue.pk,expected_version_id=proposal.base_version_id)
        self.assertEqual(Issue.objects.count(),1)
        self.assertFalse(ProposalDecision.objects.filter(proposal=proposal).exists())
        issue.refresh_from_db()
        self.accept(proposal,target_issue_id=issue.pk,expected_version_id=issue.current_version_id)
        self.assertEqual(Issue.objects.count(),1)
        self.assertEqual(issue.article_links.count(),2)

    def test_new_issue_acceptance_rechecks_identifiers_after_analysis(self):
        proposal=self.analyze().result.proposals.get()
        # Another consultant accepted the same issue while this proposal waited.
        clone=IssueProposal.objects.create(result=proposal.result,position=1,content=proposal.content,matching=proposal.matching)
        first=self.accept(clone)
        with self.assertRaises(ValidationError):
            self.accept(proposal)
        self.accept(proposal,target_issue_id=first.issue_version.issue_id,expected_version_id=first.issue_version_id)
        self.assertEqual(Issue.objects.count(),1)

    def test_invalid_outputs_roll_back_results_and_sanitize_errors(self):
        for mutate in [lambda data:data['output']['issues'][0].update(severity='invented'),
                       lambda data:data['output']['issues'][0]['citations'][0].update(quote='Not in article'),
                       lambda data:data['output']['issues'][0].update(target_issue_id=999),
                       lambda data:data['output']['issues'][0].update(identifiers=['CVE-2026-99999'])]:
            data=output();mutate(data)
            ids=queue_articles([self.article.pk],retry_failed=True)
            if not ids:  # Retry ceiling is separately tested; use another policy.
                with override_settings(NEWS_ANALYSIS_MODEL='synthetic-'+str(AnalysisRun.objects.count())):
                    ids=queue_articles([self.article.pk])
                    run=process_run(ids[0],call=lambda payload:data)
            else:
                run=process_run(ids[0],call=lambda payload:data)
            self.assertEqual(run.status,'failed')
            self.assertNotIn('CVE-',run.error)
        self.assertFalse(AnalysisResult.objects.exists())
        self.assertFalse(IssueProposal.objects.exists())

    @override_settings(NEWS_ANALYSIS_DAILY_CENTS=25)
    def test_budgets_retries_and_interruption_recovery(self):
        ids=queue_articles([self.article.pk])
        def fail(payload):
            raise RuntimeError('synthetic-secret')
        run=process_run(ids[0],call=fail)
        self.assertNotIn('synthetic-secret',run.error)
        self.assertEqual(queue_articles([self.article.pk]),[])
        retry=queue_articles([self.article.pk],retry_failed=True)[0]
        with self.assertRaises(ValidationError):
            process_run(retry,call=lambda payload:output())
        self.assertEqual(AnalysisBudget.objects.get().reserved_cents,25)
        AnalysisRun.objects.filter(pk=retry).update(status='running',started_at=timezone.now()-timedelta(minutes=6))
        self.assertEqual(recover_expired(),1)
        third=queue_articles([self.article.pk],retry_failed=True)[0]
        AnalysisRun.objects.filter(pk=third).update(status='failed')
        self.assertEqual(queue_articles([self.article.pk],retry_failed=True),[])

    def test_history_is_immutable_in_models_and_database(self):
        run=self.analyze()
        proposal=run.result.proposals.get()
        decision=self.accept(proposal)
        for record in [self.article.current_revision,run.result,proposal,decision,IssueArticleLink.objects.get()]:
            with self.assertRaises(ValidationError):
                record.save()
            with self.assertRaises(ValidationError):
                type(record).objects.filter(pk=record.pk).delete()
            with self.assertRaises(IntegrityError),transaction.atomic(),connection.cursor() as cursor:
                cursor.execute('DELETE FROM '+connection.ops.quote_name(record._meta.db_table)+' WHERE id=%s',[record.pk])
        with self.assertRaises(IntegrityError),transaction.atomic():
            AnalysisRun.objects.filter(pk=run.pk).update(input_snapshot={'changed':True})

    def test_staff_cannot_accept_without_explicit_permissions(self):
        user=get_user_model().objects.create_user('analysis-staff',is_staff=True)
        proposal=self.analyze().result.proposals.get()
        with self.assertRaises(PermissionDenied):
            decide_proposal(proposal=proposal,actor=user,decision='accept',rationale='Synthetic')
        self.client.force_login(user)
        for model in ['article','analysisrun','issueproposal','proposaldecision','issuearticlelink']:
            self.assertEqual(self.client.get('/admin/news/'+model+'/').status_code,403)

    def test_rejection_retains_output_and_no_issue(self):
        proposal=self.analyze().result.proposals.get()
        decide_proposal(proposal=proposal,actor=self.user,decision='reject',rationale='Insufficient evidence')
        self.assertFalse(Issue.objects.exists())
        self.assertEqual(proposal.decision.decision,'reject')

    @override_settings(NEWS_ANALYSIS_ENABLED=False)
    def test_manual_cli_one_some_all_and_disabled_worker(self):
        output_stream=StringIO()
        with self.assertNumQueries(0),patch('news.management.commands.analyze_news.time.sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                call_command('analyze_news',loop=True,stdout=output_stream)
        call_command('analyze_news',article=[self.article.pk],queue_only=True,stdout=StringIO())
        self.assertEqual(AnalysisRun.objects.count(),1)
        call_command('analyze_news',all_unanalyzed=True,queue_only=True,stdout=StringIO())
        self.assertEqual(AnalysisRun.objects.count(),1)
        with patch('news.analysis.provider',return_value=output()):
            # process_run receives its provider by default at definition time;
            # patch the command boundary to keep the CLI test offline.
            with patch('news.management.commands.analyze_news.process_run',side_effect=lambda pk:process_run(pk,call=lambda payload:output())):
                call_command('analyze_news',queued=True,stdout=StringIO())
        self.assertEqual(AnalysisRun.objects.get().status,'succeeded')
        with self.assertRaises(CommandError):
            call_command('analyze_news',article=[999],queue_only=True)

    def test_manual_drain_queues_all_records_in_small_batches(self):
        for suffix in ['second','third']:
            scan_source(self.source.pk,lambda url,suffix=suffix:RSS.replace(b'/advisory',('/'+suffix).encode()))
        call_command('analyze_news',all_unanalyzed=True,drain=True,max_records=1,queue_only=True,stdout=StringIO())
        self.assertEqual(AnalysisRun.objects.count(),3)
        self.assertFalse(AnalysisBudget.objects.exists())
        call_command('analyze_news',article=[self.article.pk],queue_only=True,stdout=StringIO())
        self.assertEqual(AnalysisRun.objects.count(),3)

    def test_retracted_association_does_not_supply_future_link_match(self):
        from .analysis import candidates
        proposal=self.analyze().result.proposals.get()
        decision=self.accept(proposal,content={'name':'Unrelated name','identifiers':''})
        revision=self.article.current_revision
        self.assertTrue(candidates(revision))
        IssueArticleLink.objects.create(issue=decision.issue_version.issue,revision=revision,
            relationship='retracts',actor=self.user,rationale='Incorrect source association')
        self.assertEqual(candidates(revision),[])

    def test_provider_deadline_and_no_tool_capabilities(self):
        with patch('news.analysis.subprocess.run') as request:
            request.return_value.returncode=0
            request.return_value.stdout=json.dumps(output()).encode()
            provider({})
            self.assertEqual(request.call_args.kwargs['timeout'],60)
        received=[]
        process_run(queue_articles([self.article.pk])[0],call=lambda payload:(received.append(payload) or output()))
        self.assertNotIn('tools',received[0])
        self.assertNotIn('customer',received[0]['messages'][1]['content'])

    def test_admin_decision_is_csrf_protected_and_records_edits(self):
        proposal=self.analyze().result.proposals.get()
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        path=f'/admin/news/proposaldecision/add/?proposal={proposal.pk}'
        response=client.get(path)
        self.assertEqual(response.status_code,200)
        form=response.context['adminform'].form
        data={'proposal':proposal.pk,'versions':form.initial['versions'],'decision':'accept','rationale':'Reviewed synthetic advice',
              'name':'Edited synthetic issue','severity':'medium','kind':'vulnerability','remediation':'Reviewed correction','description':'Synthetic','identifiers':'CVE-2026-12345','target_issue':''}
        self.assertEqual(client.post(path,data).status_code,403)
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(path,{**data,'csrfmiddlewaretoken':token},HTTP_ORIGIN='https://foreign.test').status_code,403)
        response=client.post(path,{**data,'csrfmiddlewaretoken':token},HTTP_ORIGIN='http://testserver')
        self.assertEqual(response.status_code,302,response.content[:3000])
        self.assertEqual(ProposalDecision.objects.get().issue_version.name,'Edited synthetic issue')


from unittest import skipUnless
from django.test import TransactionTestCase


@skipUnless(connection.vendor=='postgresql','Review locking requires PostgreSQL; exercised in CI.')
class AnalysisConcurrencyTests(TransactionTestCase):
    def test_two_publishers_cannot_accept_the_same_cve_as_new_issues(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        user=get_user_model().objects.create_superuser('concurrent-analysis',password='synthetic-password')
        proposal_ids=[]
        with patch.dict('os.environ',{'NEWS_ANALYSIS_API_KEY':'synthetic-key'}):
            for host in ['one.test','two.test']:
                source=Source.objects.create(name=host,url=f'https://{host}/',feed_url=f'https://{host}/rss')
                scan_source(source.pk,lambda url:RSS.replace(b'example.test',host.encode()))
                article=Article.objects.get(source=source)
                run=process_run(queue_articles([article.pk])[0],call=lambda payload:output())
                proposal_ids.append(run.result.proposals.get().pk)
        barrier=Barrier(2)
        def accept(pk):
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=user.pk)
                proposal=IssueProposal.objects.get(pk=pk)
                barrier.wait(timeout=10)
                try:
                    decide_proposal(proposal=proposal,actor=actor,decision='accept',rationale='Synthetic concurrency')
                    return 'accepted'
                except ValidationError:
                    return 'needs_target'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(accept,proposal_ids))
        self.assertCountEqual(results,['accepted','needs_target'])
        self.assertEqual(Issue.objects.count(),1)
        self.assertEqual(ProposalDecision.objects.count(),1)
