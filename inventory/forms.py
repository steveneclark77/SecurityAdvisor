from django import forms
from engagements.forms import StyledModelForm
from .models import InventoryItem, InventoryConnection, InventoryFollowUp, EXPOSURES

COMMON = ['name','description','owner','notes','state','provenance','last_reviewed','criticality','criticality_reason','exposures','archived']
OPERATION = ['operation_category','schedule','critical_windows','outage_tolerance','acceptable_data_loss','workaround','financial_impact','availability_impact','reputation_impact','other_impact','impact']
TECHNOLOGY = ['location','vendor_product','support_status','security_configuration','access_method','data_handling']


class ItemForm(StyledModelForm):
    exposures = forms.MultipleChoiceField(choices=EXPOSURES,required=False,widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = InventoryItem
        exclude = ['customer','kind','updated_at']

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        relevant = COMMON + (OPERATION if self.instance.kind=='operation' else TECHNOLOGY)
        if self.instance.kind=='device':
            relevant += ['quantity','operating_system']
        for name in list(self.fields):
            if name not in relevant:
                self.fields.pop(name)
        if not self.instance.pk:
            self.fields.pop('archived',None)


class ConnectionForm(StyledModelForm):
    class Meta:
        model = InventoryConnection
        exclude = ['customer']

    def __init__(self,*args,customer,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['source','target']:
            self.fields[name].queryset = InventoryItem.objects.filter(customer=customer)
        if not self.instance.pk:
            self.fields.pop('archived',None)


class FollowUpForm(StyledModelForm):
    class Meta:
        model = InventoryFollowUp
        exclude = ['customer','source_intake']

    def __init__(self,*args,customer,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['item'].queryset = InventoryItem.objects.filter(customer=customer)


class WalkthroughInventoryForm(StyledModelForm):
    class Meta:
        model = InventoryItem
        fields = ['owner']
        labels = {'owner':'Owner for new records'}
