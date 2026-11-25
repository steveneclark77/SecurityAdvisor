from django.core.exceptions import PermissionDenied

REVIEWER_GROUP='security-news reviewers'


def is_reviewer(user):
    return bool(user.is_authenticated and user.is_active and user.groups.filter(name=REVIEWER_GROUP).exists())


def require_reviewer(user):
    # Membership is explicit, including superusers; this is a shared-library role.
    if not is_reviewer(user):
        raise PermissionDenied
