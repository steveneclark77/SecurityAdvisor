from django.contrib import admin
from .models import Issue, Review, Scan, Source


class RetainedAdmin(admin.ModelAdmin):
    class Media:
        js = ["library/forms.js"]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Source)
class SourceAdmin(RetainedAdmin):
    list_display = ['name', 'enabled', 'feed_url']
    list_filter = ['enabled']
    search_fields = ['name', 'notes']


@admin.register(Issue)
class IssueAdmin(RetainedAdmin):
    list_display = ['name', 'source', 'severity', 'kind', 'discovered_at', 'review_status']
    list_filter = ['source', 'severity', 'kind']
    search_fields = ['name', 'description', 'identifiers']
    readonly_fields = ['source', 'first_scan', 'identity', 'name', 'url', 'description', 'published_at', 'discovered_at', 'last_seen_at']

    def has_add_permission(self, request):
        return False

    @admin.display(description='Latest decision')
    def review_status(self, obj):
        review = obj.reviews.order_by('-created_at', '-pk').first()
        return review.decision if review else 'Awaiting review'


@admin.register(Scan)
class ScanAdmin(RetainedAdmin):
    list_display = ['source', 'started_at', 'status', 'created_count', 'error']
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(RetainedAdmin):
    class Media:
        js = ["library/forms.js", "news/review.js"]

    list_display = ['issue', 'decision', 'actor', 'created_at']
    exclude = ['actor']
    readonly_fields = ['created_at', 'issue_snapshot']
    filter_horizontal = ['controls']

    def has_change_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.actor = request.user
        obj.issue_snapshot = {field: getattr(obj.issue, field) for field in ['name', 'url', 'description', 'severity', 'kind', 'remediation', 'identifiers']}
        super().save_model(request, obj, form, change)
