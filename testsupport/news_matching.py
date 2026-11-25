"""Synthetic matching fixtures; no feed or model requests."""
from types import SimpleNamespace
from django.contrib.auth.models import Group
from django.utils import timezone
from news.access import REVIEWER_GROUP
from news.models import Source,Scan,Article,ArticleRevision,AnalysisRun,AnalysisResult,IssueProposal


def make_proposal(user=None):
    source,_=Source.objects.get_or_create(url='https://csrf-news.test/',defaults={'name':'Synthetic CSRF news','feed_url':'https://csrf-news.test/rss'})
    scan=Scan.objects.create(source=source,feed_url=source.feed_url,status='success')
    article=Article.objects.create(source=source,first_scan=scan,url=f'https://csrf-news.test/article/{scan.pk}',identity=f'synthetic-{scan.pk}',last_seen_at=timezone.now())
    revision=ArticleRevision.objects.create(article=article,title='Synthetic matching incident',text='Synthetic product incident and remediation.',content_hash=f'synthetic-{scan.pk}',source_name=source.name,source_website=source.url)
    article.current_revision=revision;article.save(update_fields=['current_revision'])
    run=AnalysisRun.objects.create(revision=revision,model='synthetic',policy_key=f'synthetic-{scan.pk}',prompt_version='synthetic',schema_version='synthetic',status='succeeded')
    result=AnalysisResult.objects.create(run=run,output={'issues':[]},input_tokens=0,output_tokens=0,estimated_cost_cents=0)
    proposal=IssueProposal.objects.create(result=result,position=0,content={'name':'Synthetic matching incident','description':'Synthetic product incident.',
        'severity':'unknown','kind':'vulnerability','remediation':'Verify synthetic guidance.','identifiers':''},matching={'affected_products':['Synthetic product'],'affected_versions':['1.0']})
    assessment=proposal.assessments.latest('pk')
    if user:
        group,_=Group.objects.get_or_create(name=REVIEWER_GROUP)
        user.groups.add(group)
    from news.forms import sign_review, review_state
    token=sign_review(review_state(proposal,assessment))
    return SimpleNamespace(token=token,source=source,article=article,revision=revision,run=run,proposal=proposal,assessment=assessment,event=proposal.inboxevent_set.get())
