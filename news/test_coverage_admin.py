"""Admin regressions: immutable history, signed reviews and stale edits."""
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib import admin
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import TestCase,RequestFactory
from django.urls import reverse
from . import test_matching as fixtures
from . import admin as news_admin,analysis_admin,matching_admin
from .models import (Issue,IssueVersion,IssueProposal,ProposalDecision,IssueArticleLink,
                     CalibrationVersion,MatchingConfiguration,Source,Scan,Review)
from .versioning import CONTENT_FIELDS,create_version
from .match_review import act
from .forms import review_state
from .matching import MATCH_POLICY
from django.conf import settings


class AdminBoundaryTests(TestCase):
    setUp=fixtures.MatchingTests.setUp
    issue=fixtures.MatchingTests.issue
    prepared=fixtures.MatchingTests.prepared

    def request(self,query=None):
        request=RequestFactory().get('/admin/',query or {});request.user=self.user
        return request

    def test_history_and_proposal_admin_rendering(self):
        self.client.force_login(self.user);issue=self.issue()
        for model,obj in [(Issue,issue),(IssueVersion,issue.current_version),(IssueProposal,self.f.proposal)]:
            self.assertEqual(self.client.get(reverse(f'admin:news_{model._meta.model_name}_changelist')).status_code,200)
            self.assertEqual(self.client.get(reverse(f'admin:news_{model._meta.model_name}_change',args=[obj.pk])).status_code,200)
        for model in [Source,Scan,Review,IssueArticleLink]:
            self.assertEqual(self.client.get(reverse(f'admin:news_{model._meta.model_name}_changelist')).status_code,200)
        padmin=admin.site._registry[IssueProposal]
        self.assertEqual(padmin.review_status(self.f.proposal),'Pending')
        self.assertIn('Review',str(padmin.review(self.f.proposal)))
        self.assertEqual(padmin.label(self.f.proposal),self.f.proposal.content['name'])
        decision_admin=admin.site._registry[ProposalDecision]
        self.assertIn('saved proposal',decision_admin.analysis_context(None))
        initial=decision_admin.get_changeform_initial_data(self.request({'target_search':issue.name,'target':issue.pk}))
        self.assertIn(issue.pk,initial['extra_candidate_ids'])
        self.assertEqual(initial['target_issue'],issue.pk)
        request=self.request({'proposal':self.f.proposal.pk,'target':issue.pk})
        self.assertEqual(self.client.get(reverse('admin:news_proposaldecision_add'),request.GET).status_code,200)
        self.assertTrue(decision_admin.has_add_permission(request))
        self.assertIn('analysis_context',decision_admin.get_fields(request))
        self.assertIn('created_at',decision_admin.get_fields(request,ProposalDecision()))
        history=analysis_admin.HistoryAdmin(Issue,admin.site)
        self.assertFalse(history.has_add_permission(request));self.assertFalse(history.has_change_permission(request));self.assertFalse(history.has_delete_permission(request))

    def test_signed_content_review_forms_reject_tampering_and_stale_versions(self):
        issue=self.issue();proposal=self.f.proposal
        assessment=self.prepared()
        act(assessment,outcome='match',target_issue_id=issue.pk,actor=self.user,rationale='Synthetic link')
        form=analysis_admin.ProposalDecisionForm(initial={'proposal':proposal.pk,'extra_candidate_ids':[issue.pk]})
        self.assertEqual(form.initial['target_issue'],issue.pk)
        data={**proposal.content,'proposal':proposal.pk,'decision':'accept','rationale':'Synthetic','target_issue':issue.pk,'versions':form.initial['versions']}
        good=analysis_admin.ProposalDecisionForm(data)
        self.assertTrue(good.is_valid(),good.errors)
        for changes in [{'versions':'tampered'},{'name':' '},{'versions':signing.dumps({'proposal':-1,'versions':{}},salt='news-review')}]:
            invalid=analysis_admin.ProposalDecisionForm({**data,**changes});self.assertFalse(invalid.is_valid())
        create_version(issue=issue,expected_version_id=issue.current_version_id,content={'severity':'high'},actor=self.user,change_reason='Synthetic concurrent edit')
        self.assertFalse(analysis_admin.ProposalDecisionForm(data).is_valid())
        data.update(target_issue='')
        invalid=analysis_admin.ProposalDecisionForm(data)
        self.assertFalse(invalid.is_valid());self.assertIn('already has an incident',str(invalid.errors))
        self.assertFalse(ProposalDecision.objects.exists())

    def test_content_review_save_and_decided_admin_actions(self):
        self.client.force_login(self.user)
        form=analysis_admin.ProposalDecisionForm(initial={'proposal':self.f.proposal.pk})
        data={**self.f.proposal.content,'proposal':self.f.proposal.pk,'decision':'accept','rationale':'Synthetic accepted','versions':form.initial['versions']}
        bound=analysis_admin.ProposalDecisionForm(data);self.assertTrue(bound.is_valid(),bound.errors)
        record=ProposalDecision();record_admin=admin.site._registry[ProposalDecision]
        record_admin.save_model(self.request(),record,bound,False)
        self.assertIsNotNone(record.pk)
        self.assertFalse(analysis_admin.ProposalDecisionForm(data).is_valid())
        proposal=IssueProposal.objects.get(pk=self.f.proposal.pk)
        padmin=admin.site._registry[IssueProposal]
        self.assertEqual(padmin.review_status(proposal),'accept');self.assertEqual(padmin.review(proposal),'Decided')
        link_admin=admin.site._registry[IssueArticleLink]
        self.assertEqual(link_admin.get_readonly_fields(self.request()),['actor','created_at'])
        self.assertIn('revision',link_admin.get_readonly_fields(self.request(),IssueArticleLink()))
        link=IssueArticleLink(issue=record.issue_version.issue,revision=self.f.revision,relationship='supports',rationale='Another source confirmation')
        link_admin.save_model(self.request(),link,None,False)
        self.assertEqual(link.actor,self.user)

    def test_version_admin_initial_data_noop_and_reference_replacement(self):
        issue=self.issue();vadmin=admin.site._registry[IssueVersion]
        for query in [{},{'issue':'bad'},{'issue':'999999999'}]:
            with self.assertRaises(Http404): vadmin.get_changeform_initial_data(self.request(query))
        self.assertEqual(vadmin.get_changeform_initial_data(self.request({'issue':issue.pk}))['name'],issue.name)
        self.assertIn('base_version',vadmin.get_fields(self.request()))
        self.assertIn('supporting_references',vadmin.get_fields(self.request(),issue.current_version))
        form=news_admin.VersionForm({'issue':issue.pk,'base_version':-1,'name':'Synthetic','severity':'unknown','kind':'vulnerability','change_reason':'Stale'})
        self.assertFalse(form.is_valid());self.assertIn('changed',str(form.errors))
        # Real save_related workflow, including inline deletion/empty rows.
        values={key:getattr(issue.current_version,key) for key in CONTENT_FIELDS}
        values.update(issue=issue,base_version=issue.current_version_id,inherit_references=False,change_reason='Reference addition')
        form=SimpleNamespace(cleaned_data=values,instance=IssueVersion())
        formset=SimpleNamespace(cleaned_data=[{}, {'DELETE':True}, {'source':None},
            {'source':self.f.source,'source_url':self.f.article.url,'notes':'Synthetic reference'}])
        vadmin.save_model(self.request(),form.instance,form,False)
        vadmin.save_related(self.request(),form,[formset],False)
        self.assertEqual(form.instance.references.count(),1)
        self.assertIn('Synthetic reference',str(vadmin.supporting_references(form.instance)))
        issue.refresh_from_db();values['base_version']=issue.current_version_id;values['inherit_references']=True
        vadmin.save_related(self.request(),form,[],False)
        self.assertTrue(form.instance._unchanged)
        with patch.object(vadmin,'message_user') as message:
            result=vadmin.response_add(self.request(),form.instance)
            self.assertEqual(result.status_code,302);message.assert_called_once()
        self.assertIsNone(vadmin.log_addition(self.request(),form.instance,'unchanged'))
        self.assertFalse(admin.site._registry[Issue].has_change_permission(self.request()))
        for model in [Scan,IssueVersion]: self.assertFalse(admin.site._registry[model].has_change_permission(self.request()))

    def test_matching_admin_configuration_and_calibration_build(self):
        request=self.request();config_admin=admin.site._registry[MatchingConfiguration]
        form=matching_admin.ConfigurationForm({'active_calibration':'','autonomous_enabled':True})
        self.assertFalse(form.is_valid())
        version=CalibrationVersion.objects.create(name='Synthetic evaluated',policy_version=MATCH_POLICY,dataset_hash='x',label_ids=[],created_by=self.user,
            metrics={'embedding_model':settings.NEWS_EMBEDDING_MODEL,'buckets':{'synthetic':{'eligible':True}}})
        form=matching_admin.ConfigurationForm({'active_calibration':version.pk,'autonomous_enabled':True})
        self.assertTrue(form.is_valid(),form.errors)
        config=MatchingConfiguration.objects.get(pk=1);config_admin.save_model(request,config,form,True)
        self.assertTrue(config.autonomous_enabled)
        cal_admin=admin.site._registry[CalibrationVersion]
        self.assertTrue(cal_admin.has_add_permission(request));self.assertEqual(cal_admin.get_fields(request),['name'])
        self.assertEqual(cal_admin.get_readonly_fields(request),[])
        obj=CalibrationVersion();cal_admin.save_model(request,obj,SimpleNamespace(cleaned_data={'name':'Synthetic admin build'}),False)
        self.assertIsNotNone(obj.pk);self.assertIn('created_at',cal_admin.get_fields(request,obj))
        self.assertIn('created_by',cal_admin.get_readonly_fields(request,obj))
