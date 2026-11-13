"""Consistent identifying-column tie-breakers for application admin tables."""
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from .table_sorting import text_order


class IdentifiedChangeList(ChangeList):
    def _get_deterministic_ordering(self, ordering):
        # Django calls this before adding its automatic primary-key fallback.
        # Preserve selected columns/directions, then identify tied records.
        return [*ordering, text_order(self.model_admin.sort_identity).asc(), 'pk']


class IdentifiedAdmin(admin.ModelAdmin):
    sort_identity = 'name'

    def get_changelist(self, request, **kwargs):
        return IdentifiedChangeList
