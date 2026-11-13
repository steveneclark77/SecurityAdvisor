"""Database ordering expressions shared by the scoped, paginated record browsers."""
import re
from django.db.models import Case, CharField, TextField, Value, When
from django.db.models.functions import Coalesce, Concat, Lower, NullIf


def sort_token(raw, column_count):
    if raw and len(raw) <= 12 and re.fullmatch(r'-?[0-9]+', raw) and 0 <= int(raw.lstrip('-')) < column_count:
        return ('-' if raw.startswith('-') else '') + str(int(raw.lstrip('-')))
    return ''


def text_order(field, fallback=None):
    """Case-insensitive text ordering, optionally matching a displayed blank label."""
    expression = field
    if fallback is not None:
        expression = Coalesce(NullIf(field, Value('')), Value(fallback), output_field=TextField())
    return Lower(expression)


def choice_order(field, choices):
    return text_order(Case(*(When(**{field: key}, then=Value(label)) for key, label in choices),
                           default=Value(''), output_field=CharField()))


def owner_order(field):
    return text_order(Case(When(**{field + '__isnull': True}, then=Value('Unassigned')),
                           default=Concat(field + '__first_name', Value(' '), field + '__last_name')))
