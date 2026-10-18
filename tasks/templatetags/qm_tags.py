import re
from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.dateformat import format as date_format

register = template.Library()

# User preference -> Django date format string
DATE_FORMATS = {
    'DD/MM/YYYY': 'd/m/Y',
    'MM/DD/YYYY': 'm/d/Y',
    'YYYY-MM-DD': 'Y-m-d',
}
TIME_FORMAT = 'g:i A'

# Leading emoji / symbols in old server messages ("✅ Task created") look noisy
# next to the toast icon, so strip them.
_LEADING_SYMBOLS = re.compile(r'^[\W_]+(?=\w|")', re.UNICODE)


def _pref(context):
    profile = context.get('qm_profile')
    pref = getattr(profile, 'date_format', '') if profile else ''
    return DATE_FORMATS.get(pref, 'd/m/Y')


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def among(value, options):
    """`url_name|among:"a b c"` is True when value is one of the words."""
    return str(value) in str(options).split()


@register.filter
def clean_msg(message):
    text = str(message).strip()
    cleaned = _LEADING_SYMBOLS.sub('', text).strip()
    return cleaned or text


@register.simple_tag(takes_context=True)
def fmt_date(context, value, with_time=False):
    """A date in the user's chosen format (e.g. 17/10/2026)."""
    if not value:
        return ''
    if hasattr(value, 'tzinfo') and getattr(value, 'hour', None) is not None:
        value = timezone.localtime(value)
    fmt = _pref(context) + (f', {TIME_FORMAT}' if with_time else '')
    return date_format(value, fmt)


def friendly_when(value, date_fmt='d/m/Y'):
    if not value:
        return ''
    local = timezone.localtime(value)
    today = timezone.localdate()
    days = (local.date() - today).days
    time_part = date_format(local, TIME_FORMAT)
    if days == 0:
        return f'Today, {time_part}'
    if days == 1:
        return f'Tomorrow, {time_part}'
    if days == -1:
        return f'Yesterday, {time_part}'
    if 1 < days < 7:
        return f'{date_format(local, "D")}, {time_part}'
    return f'{date_format(local, date_fmt)}, {time_part}'


@register.simple_tag(takes_context=True)
def when(context, value):
    """
    A date that's easy to read at a glance:
    "Today, 7:00 PM", "Tomorrow, 9:00 AM", "Yesterday, 11:59 PM",
    "Wed, 9:00 AM" (this week), otherwise the user's date format.
    """
    return friendly_when(value, _pref(context))


@register.filter
def day_offset(value):
    """-1 overdue/past day, 0 today, 1 later; None if no date."""
    if not value:
        return None
    days = (timezone.localtime(value).date() - timezone.localdate()).days
    return 0 if days == 0 else (1 if days > 0 else -1)


@register.filter
def minutes_before(alarm_time, due_date):
    """How many minutes before the due date an alarm is set (for the edit form)."""
    if not alarm_time or not due_date:
        return ''
    return int((due_date - alarm_time) / timedelta(minutes=1))


@register.filter
def percent(part, whole):
    try:
        return min(100, round(part / whole * 100)) if whole else 0
    except (TypeError, ZeroDivisionError):
        return 0


@register.filter
def initial(text):
    text = str(text or '').strip()
    return text[:1].upper() if text else '?'
