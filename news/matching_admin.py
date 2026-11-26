from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .analysis_admin import HistoryAdmin
from .models import (MatchingConfiguration, MatchingConfigurationEvent, CalibrationVersion,
                     MatchAssessment, MatchDecision, MatchFeedback, MatchComparison, InboxEvent,
                     DigestDelivery, EmbeddingAttempt)
from .calibration import configure, build_calibration


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model=MatchingConfiguration
        fields=['active_calibration','autonomous_enabled']

    def clean(self):
        data=super().clean()
        calibration=data.get('active_calibration')
        if data.get('autonomous_enabled'):
            from .matching import MATCH_POLICY
            from django.conf import settings
            from .calibration import current_labels
            if (not calibration or calibration.policy_version!=MATCH_POLICY or
                calibration.metrics.get('embedding_model')!=settings.NEWS_EMBEDDING_MODEL or
                not any(item.get('eligible') for item in calibration.metrics.get('buckets',{}).values()) or
                set(current_labels().filter(pk__in=calibration.label_ids).values_list('pk',flat=True))!=set(calibration.label_ids)):
                raise ValidationError('Select an evaluated, compatible calibration with supported >=90% buckets and uncorrected labels.')
        return data


@admin.register(MatchingConfiguration)
class MatchingConfigurationAdmin(admin.ModelAdmin):
    change_form_template='admin/news/matching_configuration.html'
    form=ConfigurationForm
    readonly_fields=['catalog_generation','index_ready_generation','index_ready_model','updated_by','updated_at']
    class Media:
        js=['library/forms.js','news/matching-config.js']
    def has_module_permission(self,request): return request.user.is_active and request.user.is_superuser
    def has_view_permission(self,request,obj=None): return self.has_module_permission(request)
    def has_change_permission(self,request,obj=None): return self.has_module_permission(request)
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def save_model(self,request,obj,form,change):
        saved=configure(actor=request.user,calibration=form.cleaned_data['active_calibration'],autonomous=form.cleaned_data['autonomous_enabled'])
        obj.__dict__.update(saved.__dict__)


@admin.register(CalibrationVersion)
class CalibrationAdmin(HistoryAdmin):
    class Media:
        js=['library/forms.js']
    sort_identity='name'
    list_display=['name','created_at','created_by','policy_version']
    def has_add_permission(self,request): return request.user.is_active and request.user.is_superuser
    def get_fields(self,request,obj=None): return super().get_readonly_fields(request,obj) if obj else ['name']
    def get_readonly_fields(self,request,obj=None): return super().get_readonly_fields(request,obj) if obj else []
    def save_model(self,request,obj,form,change):
        result=build_calibration(form.cleaned_data['name'],request.user)
        obj.__dict__.update(result.__dict__)


for model,identity in [(MatchingConfigurationEvent,'reason'),(MatchAssessment,'proposal__result__run__revision__title'),
        (MatchDecision,'rationale'),(MatchFeedback,'rationale'),(MatchComparison,'policy_version'),
        (InboxEvent,'title'),(DigestDelivery,'status'),(EmbeddingAttempt,'model')]:
    # One read-only history implementation; all operational mutations use services.
    admin.site.register(model,type(model.__name__+'HistoryAdmin',(HistoryAdmin,),{'sort_identity':identity}))
