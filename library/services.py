from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Baseline, Control, Profile, Modifier

@transaction.atomic
def create_baseline(*, user, version, coverage_gaps):
    if not user.is_active or not user.is_staff:
        raise PermissionError('Consultant access required.')
    controls = list(Control.objects.prefetch_related('profiles','modifiers','actions'))
    if not controls or not coverage_gaps.strip():
        raise ValidationError('Controls and a coverage-gap statement are required.')
    return Baseline.objects.create(version=version,created_by=user,coverage_gaps=coverage_gaps,snapshot={'controls':[c.snapshot() for c in controls], 'profiles':list(Profile.objects.values_list('name',flat=True)), 'modifiers':list(Modifier.objects.order_by('name').values_list('name',flat=True))})

@transaction.atomic
def approve_baseline(*, pk, user, note):
    if not user.is_active or not user.is_staff:
        raise PermissionError('Consultant access required.')
    baseline = Baseline.objects.select_for_update().get(pk=pk)
    if baseline.approved_at:
        raise ValidationError('This version is already approved. Create a new version for changes.')
    if not note.strip():
        raise ValidationError('Record your review and approval rationale.')
    baseline.approval_note = note.strip()
    baseline.approved_by = user
    baseline.approved_at = timezone.now()
    baseline.save(update_fields=['approval_note','approved_by','approved_at'])
    from engagements.services import flag_reassessments
    flag_reassessments(baseline)
    return baseline
