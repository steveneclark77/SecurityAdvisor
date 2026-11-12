from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Issue, IssueVersion, IssueVersionReference, Source

CONTENT_FIELDS = ['name', 'url', 'description', 'published_at', 'severity', 'kind', 'remediation', 'identifiers']
REFERENCE_FIELDS = ['source_id', 'source_name', 'source_website', 'source_url', 'source_published_at', 'notes']


def reference_data(version):
    return list(version.references.order_by('source_url').values(*REFERENCE_FIELDS)) if version else []


@transaction.atomic
def create_version(*, issue, expected_version_id, content, actor, change_reason, origin='consultant_edit', references=None):
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    if issue.current_version_id != expected_version_id:
        raise ValidationError('This issue changed while you were editing. Reload the latest version before saving.')
    if not change_reason.strip():
        raise ValidationError('A change reason is required.')
    if origin == 'consultant_edit' and actor is None:
        raise ValidationError('Consultant edits require an actor.')
    previous = issue.current_version
    references = reference_data(previous) if references is None else references
    references = [dict(ref) for ref in references]
    for ref in references:
        if not ref.get('source_name'):
            source = Source.objects.get(pk=ref['source_id'])
            ref.update(source_name=source.name, source_website=source.url)
        ref.setdefault('source_published_at', None)
        ref.setdefault('notes', '')
    references.sort(key=lambda ref: ref['source_url'])
    values = {field: content.get(field, getattr(previous, field, IssueVersion._meta.get_field(field).get_default())) for field in CONTENT_FIELDS}
    # Fully compare content and provenance; a routine sighting is not a version.
    if previous and all(getattr(previous, field) == value for field, value in values.items()) and reference_data(previous) == references:
        return previous
    version = IssueVersion(issue=issue, version_number=previous.version_number + 1 if previous else 1,
                           **values, created_by=actor, change_reason=change_reason, origin=origin)
    version.full_clean()
    version.save()
    for reference in references:
        ref = IssueVersionReference(version=version, **reference)
        ref.full_clean()
        ref.save()
    issue.current_version = version
    issue.save(update_fields=['current_version'])
    return version
