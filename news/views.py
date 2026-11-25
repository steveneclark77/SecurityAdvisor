from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from library.record_browser import page_selection
from library.table_sorting import text_order
from .access import require_reviewer
from .forms import MatchReviewForm
from .models import InboxEvent, InboxReceipt, Issue, IssueArticleLink, IssueProposal
from .match_review import act
from .inbox import unread_events


def event_url(event):
    from django.urls import reverse
    if event.kind=='pending' and event.proposal_id:
        return reverse('news_match_review',args=[event.proposal_id])
    if event.issue_id:
        return reverse('news_issue_articles',args=[event.issue_id])
    return reverse('news_inbox')


@login_required
def inbox(request):
    require_reviewer(request.user)
    records=InboxEvent.objects.all()
    if request.GET.get('show')!='all':
        records=unread_events(request.user)
    query=request.GET.get('q','').strip()[:200]
    if query:
        records=records.filter(title__icontains=query)
    browser=page_selection(records.order_by('-pk'),request.GET,{'show':request.GET.get('show',''),'q':query},
        row_values=lambda item:(item.title,[item.kind,item.created_at]),columns=['Type','Created'],
        ordering=[[text_order('title')],[text_order('kind')],[F('created_at')]])
    for row in browser['records']:
        row['destination']=event_url(row['item'])
    return render(request,'news/inbox.html',{**browser,'query':query,'show_all':request.GET.get('show')=='all',
        'unread':unread_events(request.user).count()})


@login_required
@require_POST
def inbox_read(request):
    require_reviewer(request.user)
    ids=request.POST.getlist('event')[:50]
    valid=[int(value) for value in ids if value.isdecimal() and len(value)<19]
    if not valid:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest('Choose at least one notification.')
    for event in InboxEvent.objects.filter(pk__in=valid):
        InboxReceipt.objects.get_or_create(event=event,user=request.user)
    return redirect('news_inbox')


@login_required
@require_http_methods(["GET","POST"])
@transaction.atomic
def match_review(request,pk):
    require_reviewer(request.user)
    proposal=get_object_or_404(IssueProposal,pk=pk)
    assessment=proposal.assessments.order_by('-pk').first()
    if not assessment:
        return render(request,'news/review_waiting.html',{'proposal':proposal})
    query=request.GET.get('q','').strip()[:200]
    extra=list(Issue.objects.filter(Q(current_version__name__icontains=query)|Q(current_version__identifiers__icontains=query)).order_by('pk').values_list('pk',flat=True)[:20]) if query else []
    form=MatchReviewForm(request.POST or None,proposal=proposal,assessment=assessment,extra_ids=extra)
    if request.method=='POST' and form.is_valid():
        data=form.cleaned_data
        try:
            with transaction.atomic():
                act(assessment,outcome=data['outcome'],actor=request.user,target_issue_id=data['target'].pk if data.get('target') else None,
                    rationale=data['rationale'],expected_decision_id=data['expected_decision_id'],expected_identity=data.get('expected_identity'),
                    content={key:data[key] for key in ['name','description','severity','kind','remediation','identifiers']})
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            messages.success(request,'Matching decision recorded. Existing issue content was not changed by linking.')
            return redirect('news_inbox')
    return render(request,'news/match_review.html',{'proposal':proposal,'assessment':assessment,'form':form,
        'previous':proposal.match_decisions.select_related('actor','issue').order_by('-pk').first(),
        'candidates':assessment.evidence.get('comparisons',[]),'query':query})


@login_required
def issue_articles(request,pk):
    require_reviewer(request.user)
    issue=get_object_or_404(Issue,pk=pk)
    links=IssueArticleLink.objects.filter(issue=issue).select_related('revision__article','actor').order_by('-pk')
    history=request.GET.get('history')=='yes'
    if not history:
        latest=IssueArticleLink.objects.filter(issue=issue,revision__article_id=OuterRef('revision__article_id')).order_by('-pk')
        links=links.annotate(latest_id=Subquery(latest.values('pk')[:1])).filter(pk=F('latest_id'),relationship='supports')
    query=request.GET.get('q','').strip()[:200]
    if query:
        links=links.filter(Q(revision__title__icontains=query)|Q(revision__source_name__icontains=query))
    browser=page_selection(links,request.GET,{'q':query,'history':'yes' if history else ''},columns=['Publisher','Relationship','Recorded'],
        row_values=lambda item:(item.revision.title,[item.revision.source_name,item.relationship,item.created_at]),
        ordering=[[text_order('revision__title')],[text_order('revision__source_name')],[text_order('relationship')],[F('created_at')]])
    return render(request,'news/issue_articles.html',{'issue':issue,**browser,'query':query,'history':history})
