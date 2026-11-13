"""Contact ownership eligibility shared by models, forms and choice refresh."""
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Contact
from django.urls import reverse
from urllib.parse import urlencode


def scope_for(instance):
    if instance._meta.app_label == 'inventory':
        return {'customer_id': instance.customer_id}
    if instance._meta.model_name == 'actionresult':
        return {'engagement_id': instance.assessment.engagement_id}
    if instance._meta.model_name == 'remediation':
        return {'engagement_id': instance.finding.engagement_id}
    return {'engagement_id': instance.engagement_id}


def owner_contacts(*, customer_id=None, engagement_id=None, retained_id=None):
    scope = {'engagement_links__engagement_id': engagement_id} if engagement_id else {'engagement_links__engagement__customer_id': customer_id}
    if not (customer_id or engagement_id):
        return Contact.objects.none()
    eligible = Q(archived=False, engagement_links__active=True)
    if retained_id:
        eligible |= Q(pk=retained_id)
    return Contact.objects.filter(Q(**scope) & eligible).distinct()


def owner_field(instance):
    return 'investigation_owner' if instance._meta.model_name == 'actionresult' else 'owner'


def configure_form(form):
    name = owner_field(form.instance)
    if name not in form.fields:
        return
    existing = getattr(form.instance, name + '_id', None)
    form.fields[name].queryset = owner_contacts(**scope_for(form.instance), retained_id=existing)
    form.fields[name].empty_label = 'Unassigned'
    form.fields[name].label_from_instance = owner_label
    if 'notes' in form.fields:
        ordered = [key for key in form.fields if key != 'notes']
        ordered.insert(ordered.index(name) + 1, 'notes')
        form.order_fields(ordered)
    form.fields[name].help_text = 'One accountable contact. Describe other participants in Notes. Archived/inactive current owners may be retained; choose an active contact for reassignment.'
    scope = scope_for(form.instance)
    form.fields[name].widget.attrs.update({
        'data-owner-options': reverse('owner_choices') + '?' + urlencode(scope),
        'data-owner-create': reverse('contact_new') + '?' + urlencode({'engagement': scope['engagement_id']} if scope.get('engagement_id') else {'customer': scope['customer_id']}),
    })


def validate_owner(instance):
    name = owner_field(instance)
    selected = getattr(instance, name + '_id', None)
    if not selected:
        return
    previous = type(instance).objects.filter(pk=instance.pk).values_list(name + '_id', flat=True).first() if instance.pk else None
    if not owner_contacts(**scope_for(instance), retained_id=previous).filter(pk=selected).exists():
        raise ValidationError({name: 'Choose an active contact linked to this engagement/customer.'})


def owner_snapshot(contact):
    return {'id': contact.pk, 'name': str(contact), 'email': contact.email} if contact else None


def owner_label(contact):
    detail = contact.email or contact.office_phone or contact.cell_phone
    return f'{contact} · {detail}' + (' · Archived' if contact.archived else '')
