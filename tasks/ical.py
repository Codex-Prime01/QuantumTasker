"""
Calendar files (.ics), written by hand. The format (RFC 5545) is plain text,
so there's no need for an extra package.

Two uses:
- one task -> a file the phone's calendar imports, with its own alarm
  (so it rings even when Quantum is closed or offline)
- all upcoming tasks -> a feed the phone subscribes to and refreshes
"""
from datetime import timedelta, timezone as dt_timezone

from django.utils import timezone

PRODID = '-//Quantum Manager//Tasks//EN'
EVENT_LENGTH = timedelta(minutes=30)

# How our repeat choices are written in calendar language
RRULES = {
    'daily': 'FREQ=DAILY',
    'weekly': 'FREQ=WEEKLY',
    'biweekly': 'FREQ=WEEKLY;INTERVAL=2',
    'monthly': 'FREQ=MONTHLY',
    'yearly': 'FREQ=YEARLY',
}


def _escape(text):
    """Commas, semicolons, backslashes and new lines have special meaning in .ics text."""
    return (
        str(text or '')
        .replace('\\', '\\\\')
        .replace(';', '\\;')
        .replace(',', '\\,')
        .replace('\r\n', '\\n')
        .replace('\n', '\\n')
    )


def _fold(line):
    """Lines longer than 75 bytes must wrap, with a space starting each extra line."""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    parts, chunk = [], b''
    for ch in line:
        b = ch.encode('utf-8')
        # 74 on follow-up lines, because the leading space counts too
        limit = 75 if not parts else 74
        if len(chunk) + len(b) > limit:
            parts.append(chunk.decode('utf-8'))
            chunk = b''
        chunk += b
    parts.append(chunk.decode('utf-8'))
    return '\r\n '.join(parts)


def _utc(value):
    return value.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def task_event(task, base_url):
    """The VEVENT lines for one task (it must have a due date)."""
    start = task.due_date
    link = f'{base_url}/update/{task.id}/'
    notes = (task.description or '').strip()
    description = f'{notes}\n\nOpen in Quantum: {link}' if notes else f'Open in Quantum: {link}'
    lines = [
        'BEGIN:VEVENT',
        f'UID:task-{task.id}@quantum-manager',
        f'DTSTAMP:{_utc(timezone.now())}',
        f'DTSTART:{_utc(start)}',
        f'DTEND:{_utc(start + EVENT_LENGTH)}',
        f'SUMMARY:{_escape(task.title)}',
        f'DESCRIPTION:{_escape(description)}',
        f'URL:{link}',
        'STATUS:CONFIRMED',
    ]
    if task.is_recurring and task.recurring_frequency != 'none':
        if task.recurring_frequency == 'custom':
            lines.append(f'RRULE:FREQ=DAILY;INTERVAL={max(1, task.recurring_interval or 1)}')
        elif task.recurring_frequency in RRULES:
            lines.append(f'RRULE:{RRULES[task.recurring_frequency]}')
    if task.alarm_enabled and task.alarm_time:
        minutes = max(0, int((start - task.alarm_time).total_seconds() // 60))
        lines += [
            'BEGIN:VALARM',
            'ACTION:DISPLAY',
            f'DESCRIPTION:{_escape(task.title)}',
            f'TRIGGER:-PT{minutes}M',
            'END:VALARM',
        ]
    lines.append('END:VEVENT')
    return lines


def build_calendar(tasks, base_url, name='Quantum Manager', feed=False):
    """A whole .ics file. Tasks without a due date are skipped."""
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:{PRODID}',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_escape(name)}',
    ]
    if feed:
        # Ask calendar apps to check back often (they decide in the end)
        lines += ['REFRESH-INTERVAL;VALUE=DURATION:PT15M', 'X-PUBLISHED-TTL:PT15M']
    for task in tasks:
        if task.due_date:
            lines += task_event(task, base_url)
    lines.append('END:VCALENDAR')
    return '\r\n'.join(_fold(line) for line in lines) + '\r\n'
