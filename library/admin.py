from django.contrib import admin
from django.conf import settings
from django.db.models import Case, When, Value, CharField
from .admin_sorting import IdentifiedAdmin
from .models import Profile, Modifier, Control, Baseline, ControlAction
admin.site.site_header = f'SecurityAdvisor v{settings.APP_VERSION} · Library'
admin.site.register(Profile, IdentifiedAdmin)
admin.site.register(Modifier, IdentifiedAdmin)
class ControlActionInline(admin.StackedInline):
    model = ControlAction
    extra = 0

@admin.register(Control)
class ControlAdmin(IdentifiedAdmin):
    sort_identity = 'code'
    inlines = [ControlActionInline]
    list_display = ['code','title','function','universal']
    list_filter = ['function','universal','profiles','modifiers']
    search_fields = ['code','title','investigation','recommendation']
    filter_horizontal = ['profiles','modifiers']
@admin.register(Baseline)
class BaselineAdmin(IdentifiedAdmin):
    sort_identity = 'version'
    list_display = ['version','status','created_at','approved_at','approved_by']
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(status_label=Case(
            When(superseded_by__isnull=False,then=Value('Superseded')),
            When(approved_at__isnull=False,then=Value('Approved')),
            default=Value('Awaiting review'),output_field=CharField()))

    @admin.display(ordering='status_label', description='Status')
    def status(self, obj):
        return obj.status

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
