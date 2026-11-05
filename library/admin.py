from django.contrib import admin
from .models import Profile, Modifier, Control, Baseline, ControlAction
admin.site.site_header = 'SecurityAdvisor library'
admin.site.register(Profile)
admin.site.register(Modifier)
class ControlActionInline(admin.StackedInline):
    model = ControlAction
    extra = 0

@admin.register(Control)
class ControlAdmin(admin.ModelAdmin):
    inlines = [ControlActionInline]
    list_display = ['code','title','function','universal']
    list_filter = ['function','universal','profiles','modifiers']
    search_fields = ['code','title','investigation','recommendation']
    filter_horizontal = ['profiles','modifiers']
@admin.register(Baseline)
class BaselineAdmin(admin.ModelAdmin):
    list_display = ['version','status','created_at','approved_at','approved_by']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
