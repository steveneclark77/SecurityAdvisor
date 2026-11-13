"""Global empty-choice labels and safe field-help metadata."""
from django import forms
from django.test import SimpleTestCase
from engagements.forms import ContactForm
from inventory.forms import ItemForm
from inventory.models import InventoryItem
from .views import ApprovalForm


class FieldRenderingTests(SimpleTestCase):
    def test_model_empty_choices_are_contextual(self):
        form=ItemForm(instance=InventoryItem(kind='operation'))
        html=str(form['operation_category'])
        self.assertIn('Select an operation category',html)
        self.assertNotIn('---------',html)
        self.assertIn('data-field-info',html)
        self.assertIn('No preference',str(ContactForm()['preferred_method']))

    def test_choice_labels_preserve_semantics_and_values(self):
        class Example(forms.Form):
            status=forms.ChoiceField(choices=[('', '---------'),('unknown','Unknown')],required=False)
            filtered=forms.ChoiceField(choices=[('', 'All records'),('active','Active')])
        form=Example({'status':'unknown'})
        self.assertIn('No status specified',str(form['status']))
        self.assertIn('value="unknown" selected',str(form['status']))
        self.assertIn('All records',str(form['filtered']))
        self.assertIn('data-no-field-info',str(ApprovalForm()['confirmed']))

    def test_field_help_metadata_is_escaped(self):
        class Example(forms.Form):
            title=forms.CharField(help_text='<img src=x onerror=alert(1)>Synthetic help')
        html=str(Example()['title'])
        self.assertNotIn('<img',html)
        self.assertIn('Synthetic help',html)
