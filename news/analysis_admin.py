"""Permissioned human review using Django's existing CSRF-protected admin forms."""
import json
from django import forms
from django.contrib import admin
from django.db.models import Q
from django.core import signing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from library.admin_sorting import IdentifiedAdmin
from .models import (Article, ArticleRevision, AnalysisRun, AnalysisResult, IssueProposal,
                     ProposalDecision, IssueArticleLink, Issue, IssueVersion, Source)
from .analysis import decide_proposal, validate_new_issue


class HistoryAdmin(IdentifiedAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self,request):
        return False

    def has_change_permission(self,request,obj=None):
        return False

    def has_delete_permission(self,request,obj=None):
        return False


@admin.register(Article)
class ArticleAdmin(HistoryAdmin):
    sort_identity='url'
    list_display=['id','source','url','current_revision','last_seen_at']
    search_fields=['url','current_revision__title']
    list_filter=['source']


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(HistoryAdmin):
    sort_identity='title'
    list_display=['id','title','article','captured_at']


@admin.register(AnalysisRun)
class AnalysisRunAdmin(HistoryAdmin):
    sort_identity='revision__title'
    list_display=['id','revision','status','attempt','model','created_at']
    list_filter=['status']


@admin.register(AnalysisResult)
class AnalysisResultAdmin(HistoryAdmin):
    sort_identity='run__revision__title'
    list_display=['id','run','estimated_cost_cents','created_at']


@admin.register(IssueProposal)
class IssueProposalAdmin(HistoryAdmin):
    sort_identity='result__run__revision__title'
    list_display=['id','label','target_issue','review_status','review']

    def get_queryset(self,request):
        return super().get_queryset(request).select_related('decision')

    def label(self,obj):
        return obj.content.get('name','')

    def review_status(self,obj):
        decision=getattr(obj,'decision',None)
        return decision.decision if decision else 'Pending'

    def review(self,obj):
        if getattr(obj,'decision',None):
            return 'Decided'
        return format_html('<a class="button" href="{}?proposal={}">Review</a>',reverse('admin:news_proposaldecision_add'),obj.pk)

    def get_readonly_fields(self,request,obj=None):
        return [*super().get_readonly_fields(request,obj),'review_status','review']


class ProposalDecisionForm(forms.ModelForm):
    target_issue=forms.ModelChoiceField(Issue.objects.none(),required=False,
        empty_label='Create a new issue',help_text='Choose a candidate issue to consolidate reports, or create a new issue. Use Search issues above to find another target before editing this form.')
    versions=forms.CharField(widget=forms.HiddenInput,required=False)
    name=forms.CharField(max_length=500,required=False)
    description=forms.CharField(widget=forms.Textarea,required=False)
    severity=forms.ChoiceField(choices=IssueVersion._meta.get_field('severity').choices)
    kind=forms.ChoiceField(choices=IssueVersion._meta.get_field('kind').choices)
    remediation=forms.CharField(widget=forms.Textarea,required=False)
    identifiers=forms.CharField(widget=forms.Textarea,required=False)

    class Meta:
        model=ProposalDecision
        fields=['proposal','decision','rationale']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        # The permissioned admin constructs a bounded candidate selection from the
        # saved analysis input, plus an explicitly requested review target.
        proposal_id=self.data.get('proposal') if self.is_bound else self.initial.get('proposal')
        proposal=IssueProposal.objects.select_related('result__run').filter(pk=proposal_id).first() if str(proposal_id).isdigit() else None
        ids=[]
        if proposal:
            ids=[item['issue_id'] for item in proposal.result.run.input_snapshot.get('candidate_issues',[])]
            if proposal.target_issue_id:
                ids.append(proposal.target_issue_id)
            latest_match=proposal.match_decisions.filter(issue__isnull=False).order_by('-pk').first()
            if latest_match:
                ids.append(latest_match.issue_id)
                self.initial.setdefault('target_issue',latest_match.issue_id)
            ids.extend(self.initial.get('extra_candidate_ids',[]))
            target=self.initial.get('target_issue')
            if target:
                ids.append(target)
            # On POST the signed map supplies only the candidates displayed on GET.
            if self.is_bound:
                try:
                    signed=signing.loads(self.data.get('versions',''),salt='news-review',max_age=86400)
                    if signed['proposal']==proposal.pk:
                        ids += [int(key) for key in signed['versions']]
                except (signing.BadSignature,ValueError,TypeError):
                    pass
        self.fields['target_issue'].queryset=Issue.objects.filter(pk__in=ids).select_related('current_version')
        if not self.is_bound:
            versions={str(issue.pk):issue.current_version_id for issue in self.fields['target_issue'].queryset}
            self.initial['versions']=signing.dumps({'proposal':proposal.pk,'versions':versions},salt='news-review') if proposal else ''
            if proposal:
                self.initial.update(proposal.content)
                if 'target_issue' not in self.initial:
                    self.initial['target_issue']=proposal.target_issue_id
        self.fields['proposal'].widget=forms.HiddenInput()

    def clean(self):
        data=super().clean()
        proposal=data.get('proposal')
        Source.objects.select_for_update().order_by('pk').first()
        if proposal:
            IssueProposal.objects.select_for_update().get(pk=proposal.pk)
        if data.get('decision')=='accept':
            if not data.get('name','').strip():
                self.add_error('name','A name is required to accept a proposal.')
            try:
                signed=signing.loads(data.get('versions',''),salt='news-review',max_age=86400)
                if not proposal or signed['proposal']!=proposal.pk:
                    raise ValidationError('Review does not match this proposal; reload.')
                versions=signed['versions']
                target=data.get('target_issue')
                if target:
                    target=Issue.objects.select_for_update().get(pk=target.pk)
                if target and (str(target.pk) not in versions or versions[str(target.pk)]!=target.current_version_id):
                    raise ValidationError('Issue changed; reload the review before accepting.')
                data['expected_version_id']=versions[str(target.pk)] if target else None
                if not target:
                    if proposal.match_decisions.filter(issue__isnull=False).exists():
                        raise ValidationError('This proposal already has an incident. Select it as the target.')
                    validate_new_issue(data.get('identifiers',''))
            except signing.BadSignature:
                raise ValidationError('Review expired or invalid; reload before accepting.') from None
        proposal=data.get('proposal')
        if proposal and ProposalDecision.objects.filter(proposal=proposal).exists():
            raise ValidationError('This proposal was already decided.')
        return data


@admin.register(ProposalDecision)
class ProposalDecisionAdmin(HistoryAdmin):
    change_form_template='admin/news/proposal_review.html'
    sort_identity='proposal__result__run__revision__title'
    form=ProposalDecisionForm
    list_display=['id','proposal','decision','actor','created_at']

    class Media:
        js=['library/forms.js','news/review.js']

    def has_add_permission(self,request):
        return request.user.has_perm('news.add_proposaldecision') and bool(request.GET.get('proposal') or request.POST.get('proposal'))

    def get_fields(self,request,obj=None):
        if obj:
            return super().get_readonly_fields(request,obj)
        return ['analysis_context','proposal','decision','rationale','target_issue','versions','name','description','severity','kind','remediation','identifiers']

    def get_readonly_fields(self,request,obj=None):
        return super().get_readonly_fields(request,obj) if obj else ['analysis_context']

    def analysis_context(self,obj):
        return 'Open the saved proposal to inspect input, matching evidence and citations before deciding.'

    def render_change_form(self,request,context,add=False,change=False,form_url='',obj=None):
        proposal_id=request.GET.get('proposal') or request.POST.get('proposal')
        proposal=IssueProposal.objects.select_related('base_version','result__run__revision').filter(pk=proposal_id).first() if str(proposal_id).isdigit() else None
        context['proposal_id']=proposal_id
        context['target_search']=request.GET.get('target_search','')[:200]
        if proposal:
            base=proposal.base_version
            context['analysis_evidence']=json.dumps({
                'article_revision':proposal.result.run.revision_id,'article_title':proposal.result.run.revision.title,
                'suggested_content':proposal.content,'evidence_and_matching':proposal.matching,
                'base_version':{key:getattr(base,key) for key in ['name','description','severity','kind','remediation','identifiers']} if base else None,
            },indent=2,ensure_ascii=False)
        return super().render_change_form(request,context,add,change,form_url,obj)

    def get_changeform_initial_data(self,request):
        initial=super().get_changeform_initial_data(request)
        query=request.GET.get('target_search','').strip()[:200]
        if query:
            initial['extra_candidate_ids']=list(Issue.objects.filter(Q(current_version__name__icontains=query)|Q(current_version__identifiers__icontains=query)).order_by('pk').values_list('pk',flat=True)[:20])
        if request.GET.get('target','').isdigit():
            initial['target_issue']=int(request.GET['target'])
        return initial

    def save_model(self,request,obj,form,change):
        data=form.cleaned_data
        decision=decide_proposal(proposal=data['proposal'],actor=request.user,decision=data['decision'],rationale=data['rationale'],
            target_issue_id=data['target_issue'].pk if data.get('target_issue') else None,
            expected_version_id=data.get('expected_version_id'),
            content={key:data[key] for key in ['name','description','severity','kind','remediation','identifiers']})
        obj.__dict__.update(decision.__dict__)


@admin.register(IssueArticleLink)
class IssueArticleLinkAdmin(HistoryAdmin):
    sort_identity='revision__title'
    list_display=['id','issue','revision','relationship','actor','created_at']

    class Media:
        js=['library/forms.js']

    def has_add_permission(self,request):
        return request.user.has_perm('news.add_issuearticlelink') and request.user.has_perm('news.change_issue')

    def get_readonly_fields(self,request,obj=None):
        return super().get_readonly_fields(request,obj) if obj else ['actor','created_at']

    def save_model(self,request,obj,form,change):
        obj.actor=request.user
        super().save_model(request,obj,form,change)


from . import matching_admin  # noqa: F401, E402
