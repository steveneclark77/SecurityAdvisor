"""Display-value ordering shared by the scoped, paginated record browsers."""
import re
import unicodedata
from datetime import date, datetime


def natural_key(value):
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    text = unicodedata.normalize('NFKD', str('' if value is None else value)).casefold()
    text = ''.join(char for char in text if not unicodedata.combining(char))
    pieces = []
    for part in re.split(r'(\d+)', text):
        if part.isdecimal():
            digits = ''.join(str(unicodedata.decimal(char)) for char in part).lstrip('0')
            pieces.append((1, len(digits), digits))
        else:
            pieces.append((0, part))
    return tuple(pieces)


def sort_token(raw, column_count):
    if raw and len(raw) <= 12 and re.fullmatch(r'-?[0-9]+', raw) and 0 <= int(raw.lstrip('-')) < column_count:
        return ('-' if raw.startswith('-') else '') + str(int(raw.lstrip('-')))
    return ''
