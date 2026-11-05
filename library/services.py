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
    if baseline.superseded_by_id:
        raise ValidationError('This draft is superseded. Review its replacement instead.')
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


@transaction.atomic
def supersede_draft(*, pk, replacement_pk, user, note):
    if not user.is_active or not user.is_staff:
        raise PermissionError('Consultant access required.')
    # Lock in ID order to avoid competing revision requests deadlocking.
    locked = {b.pk:b for b in Baseline.objects.select_for_update().filter(pk__in=[pk,replacement_pk]).order_by('pk')}
    source = locked[pk]
    replacement = locked[replacement_pk]
    if source.approved_at or source.superseded_by_id:
        raise ValidationError('Only an awaiting-review draft can be superseded.')
    if replacement.pk == source.pk or replacement.created_at <= source.created_at or replacement.superseded_by_id:
        raise ValidationError('Choose a newer, active replacement snapshot.')
    if hasattr(replacement, 'replaces'):
        raise ValidationError('This replacement already supersedes another draft.')
    if not note.strip():
        raise ValidationError('Explain why this draft is being replaced.')
    source.superseded_by = replacement
    source.superseded_at = timezone.now()
    source.superseded_actor = user
    source.supersession_note = note.strip()
    source.save(update_fields=['superseded_by','superseded_at','superseded_actor','supersession_note'])
    return replacement


@transaction.atomic
def revise_draft(*, pk, user, version, coverage_gaps, revision_note):
    if not user.is_active or not user.is_staff:
        raise PermissionError('Consultant access required.')
    source = Baseline.objects.select_for_update().get(pk=pk)
    if source.approved_at or source.superseded_by_id:
        raise ValidationError('Only an awaiting-review draft can be revised.')
    replacement = create_baseline(user=user, version=version, coverage_gaps=coverage_gaps)
    return supersede_draft(pk=pk, replacement_pk=replacement.pk, user=user, note=revision_note)
