from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.views.decorators.http import require_http_methods,require_POST
from engagements.models import Customer
from engagements.views import consultant,engagement_for
from . import forms,services
from .explorer import explorer_context
from .navigation import cancel_url, list_url
from .models import InventoryItem,InventoryConnection,InventoryFollowUp,InventoryEvent,ITEM_KINDS


def customers_for(user):
    return Customer.objects.filter(assigned_users=user)


def customer_for(user,pk):
    return get_object_or_404(customers_for(user),pk=pk)


@consultant
def index(request):
    return render(request,'inventory/index.html',{'customers':customers_for(request.user)})


@consultant
def detail(request,pk):
    customer=customer_for(request.user,pk)
    return render(request,'inventory/detail.html',{'customer':customer,**explorer_context(customer,request.GET)})


def editor(request,customer,obj,form_class,title,*,scoped=False):
    back_url=cancel_url(customer,obj,request.GET.get('return_to',''))
    before=services.record_fields(obj) if obj.pk else {}
    kwargs={'instance':obj}
    if scoped:
        kwargs['customer']=customer
    form=form_class(request.POST if request.method=='POST' else None,**kwargs)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            Customer.objects.select_for_update().get(pk=customer.pk)
            saved=form.save()
            InventoryEvent.objects.create(customer=customer,actor=request.user,description=f'{title}: record {saved.pk}.',details={'before':before,'after':services.record_fields(saved)})
        return redirect(list_url(customer,saved))
    return render(request,'inventory/form.html',{'customer':customer,'form':form,'title':title,'cancel_url':back_url},status=400 if request.method=='POST' else 200)


@consultant
@require_http_methods(['GET','POST'])
def item_new(request,pk):
    customer=customer_for(request.user,pk)
    kind=request.GET.get('kind','')
    if kind not in dict(ITEM_KINDS):
        raise Http404
    return editor(request,customer,InventoryItem(customer=customer,kind=kind),forms.ItemForm,f'Create {dict(ITEM_KINDS)[kind].lower()}')


@consultant
@require_http_methods(['GET','POST'])
def item_edit(request,pk):
    obj=get_object_or_404(InventoryItem.objects.filter(customer__in=customers_for(request.user)),pk=pk)
    return editor(request,obj.customer,obj,forms.ItemForm,f'Edit {obj.name}')


@consultant
@require_http_methods(['GET','POST'])
def connection_new(request,pk):
    customer=customer_for(request.user,pk)
    return editor(request,customer,InventoryConnection(customer=customer),forms.ConnectionForm,'Connect customer records',scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def connection_edit(request,pk):
    obj=get_object_or_404(InventoryConnection.objects.filter(customer__in=customers_for(request.user)),pk=pk)
    return editor(request,obj.customer,obj,forms.ConnectionForm,'Edit connection',scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def followup_new(request,pk):
    customer=customer_for(request.user,pk)
    return editor(request,customer,InventoryFollowUp(customer=customer),forms.FollowUpForm,'Request missing environment information',scoped=True)


@consultant
@require_http_methods(['GET','POST'])
def followup_edit(request,pk):
    obj=get_object_or_404(InventoryFollowUp.objects.filter(customer__in=customers_for(request.user)),pk=pk)
    return editor(request,obj.customer,obj,forms.FollowUpForm,'Update information follow-up',scoped=True)


@consultant
@require_POST
def intake_followups(request,pk):
    engagement=engagement_for(request.user,pk)
    for intake in engagement.intakes.all():
        services.intake_followup(intake,request.user)
    return redirect(reverse('inventory_detail',args=[engagement.customer_id]))
