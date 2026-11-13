"""Shared field metadata and meaningful empty choices for every Django form."""
import re
from django import forms
from django.forms.boundfield import BoundField
from django.forms.renderers import DjangoTemplates
from django.utils.html import strip_tags

EMPTY_LABELS = {
    'owner': 'Unassigned', 'investigation_owner': 'Unassigned',
    'operation_category': 'Select an operation category',
    'preferred_method': 'No preference', 'request': 'No evidence request — recorded directly',
    'item': 'No related inventory record', 'source_intake': 'No source intake',
    'assessment': 'Select an assessment', 'baseline': 'Select a baseline',
    'replacement': 'Select a replacement baseline', 'profile': 'Select a business profile',
    'link_engagement': 'Select an engagement',
}


class AppBoundField(BoundField):
    def __init__(self, form, field, name):
        super().__init__(form, field, name)
        label = strip_tags(str(self.label)).rstrip(':')
        empty = EMPTY_LABELS.get(name, f'Select {label.lower()}' if field.required else f'No {label.lower()} specified')
        widget = field.widget
        while hasattr(widget, 'widget'):
            widget = widget.widget
        if isinstance(widget, forms.Select) and not widget.allow_multiple_selected:
            if isinstance(field, forms.ModelChoiceField):
                if field.empty_label is not None and re.fullmatch(r'[-–—]+', str(field.empty_label).strip()):
                    field.empty_label = empty
            elif field.choices:
                field.choices = [(value, empty if value == '' and re.fullmatch(r'[-–—]+', str(text).strip()) else text) for value, text in field.choices]
        if not field.widget.is_hidden:
            action = 'Choose' if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)) else ('Select' if isinstance(widget, forms.Select) else 'Enter')
            fallback = f'{action} {label.lower()}. ' + ('This field is required.' if field.required else 'This field is optional.')
            field.widget.attrs.update({'data-field-info': strip_tags(str(field.help_text)) if field.help_text else fallback,
                                       'data-field-label': label, 'data-field-id': self.auto_id})


class AppFormRenderer(DjangoTemplates):
    bound_field_class = AppBoundField
