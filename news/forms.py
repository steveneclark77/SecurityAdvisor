from django import forms
from django.core import signing
from django.core.exceptions import ValidationError
from .models import Issue, IssueVersion


def review_state(proposal,assessment,extra_ids=()):
    ids=list(extra_ids)+[row['issue_id'] for row in assessment.evidence.get('comparisons',[])]
    if proposal.target_issue_id:
        ids.append(proposal.target_issue_id)
    ids.extend(proposal.match_decisions.filter(issue__isnull=False).values_list('issue_id',flat=True))
    profiles={}
    for issue in Issue.objects.filter(pk__in=ids).order_by('pk')[:20]:
        profile=getattr(issue,'match_profile',None)
        if profile:
            profiles[str(issue.pk)]=profile.identity_hash
    previous=proposal.match_decisions.order_by('-pk').first()
    return {'proposal':proposal.pk,'assessment':assessment.pk,'previous':previous.pk if previous else None,'profiles':profiles}


def sign_review(state):
    return signing.dumps(state,salt='news-match-review')


class MatchReviewForm(forms.Form):
    token=forms.CharField(widget=forms.HiddenInput)
    outcome=forms.ChoiceField(choices=[('','Select a matching decision'),('match','Same incident — link to an issue'),('new','New incident — create an issue'),('irrelevant','Not a security issue'),('uncertain','Still uncertain')])
    target=forms.ModelChoiceField(Issue.objects.none(),required=False,empty_label='Select an existing issue')
    rationale=forms.CharField(widget=forms.Textarea,max_length=5000)
    name=forms.CharField(required=False,max_length=500)
    description=forms.CharField(required=False,widget=forms.Textarea,max_length=10000)
    severity=forms.ChoiceField(choices=IssueVersion._meta.get_field('severity').choices)
    kind=forms.ChoiceField(choices=IssueVersion._meta.get_field('kind').choices)
    remediation=forms.CharField(required=False,widget=forms.Textarea,max_length=10000)
    identifiers=forms.CharField(required=False,widget=forms.Textarea,max_length=4000)

    def __init__(self,*args,proposal,assessment,extra_ids=(),**kwargs):
        self.proposal=proposal;self.assessment=assessment
        initial={**proposal.content,'outcome':'','target':assessment.target_issue_id}
        state=review_state(proposal,assessment,extra_ids)
        initial['token']=sign_review(state)
        kwargs['initial']=initial
        super().__init__(*args,**kwargs)
        if self.is_bound:
            try:
                state=signing.loads(self.data.get('token',''),salt='news-match-review',max_age=86400)
            except signing.BadSignature:
                state={'profiles':{}}
        self.fields['target'].queryset=Issue.objects.filter(pk__in=state.get('profiles',{})).select_related('current_version')

    def clean(self):
        data=super().clean()
        try:
            state=signing.loads(data.get('token',''),salt='news-match-review',max_age=86400)
        except signing.BadSignature:
            raise ValidationError('This review expired. Reload the page.') from None
        if state.get('proposal')!=self.proposal.pk or state.get('assessment')!=self.assessment.pk:
            raise ValidationError('This review does not match the proposal.')
        if data.get('outcome')=='match':
            target=data.get('target')
            if not target:
                self.add_error('target','Select an existing issue.')
            else:
                data['expected_identity']=state['profiles'].get(str(target.pk))
        if data.get('outcome')=='new' and not data.get('name','').strip():
            self.add_error('name','A name is required for a new issue.')
        data['expected_decision_id']=state.get('previous')
        return data
