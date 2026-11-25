from django import forms
from django.contrib import admin
from .analysis_admin import HistoryAdmin
from .models import SlackTestRequest


class SlackTestForm(forms.ModelForm):
    confirm=forms.BooleanField(label='Send a real test message to securityadvisor / security-advisor-notifications',
        help_text='This explicit test works with daily digests disabled and never consumes the digest delivery window.')
    class Meta:
        model=SlackTestRequest
        fields=[]


@admin.register(SlackTestRequest)
class SlackTestRequestAdmin(HistoryAdmin):
    form=SlackTestForm
    sort_identity='origin'
    list_display=['id','origin','status','actor','created_at','finished_at','message']
    change_form_template='admin/news/slack_test_form.html'
    change_list_template='admin/news/slack_test_list.html'

    class Media:
        js=['library/forms.js']

    def has_module_permission(self,request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self,request,obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self,request):
        return self.has_module_permission(request)

    def get_fields(self,request,obj=None):
        return super().get_readonly_fields(request,obj) if obj else ['confirm']

    def get_readonly_fields(self,request,obj=None):
        return super().get_readonly_fields(request,obj) if obj else []

    def save_model(self,request,obj,form,change):
        obj.actor=request.user
        obj.origin='admin'
        obj.save()
