"""
Understands the quick-add box on the home screen, so people can type the way
they talk:

    "Call mum tomorrow 7pm"          -> due tomorrow at 19:00
    "Pay rent every month !!"        -> repeats monthly, high priority
    "Submit assignment friday 11:59pm !!!"
    "Take medicine in 30 min"
    "Gym every monday 6am"

It only reads simple, unambiguous phrases. Anything it doesn't understand stays
in the title, so nothing the user typed is lost.
"""
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
WEEKDAY_SHORT = {'mon': 0, 'tue': 1, 'tues': 1, 'wed': 2, 'thu': 3, 'thur': 3, 'thurs': 3,
                 'fri': 4, 'sat': 5, 'sun': 6}
MONTHS = {m: i + 1 for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'])}
MONTHS.update({m[:3]: n for m, n in list(MONTHS.items())})
MONTHS['sept'] = 9

PARTS_OF_DAY = {'morning': time(9, 0), 'afternoon': time(14, 0), 'evening': time(18, 0),
                'night': time(20, 0), 'tonight': time(20, 0), 'noon': time(12, 0),
                'midday': time(12, 0), 'midnight': time(23, 59)}
DEFAULT_TIME = time(9, 0)


@dataclass
class Parsed:
    title: str
    due: Optional[datetime] = None
    priority: Optional[str] = None
    repeat: Optional[str] = None
    has_time: bool = False


def _weekday_index(word):
    word = word.lower()
    if word in WEEKDAYS:
        return WEEKDAYS.index(word)
    return WEEKDAY_SHORT.get(word)


def _next_weekday(today, index, force_next=False):
    days = (index - today.weekday()) % 7
    if days == 0 or force_next:
        days = days or 7
    return today + timedelta(days=days)


def _cut(text, match):
    return (text[:match.start()] + ' ' + text[match.end():]).strip()


def parse(text, now):
    """`now` must be timezone-aware local time. Returns a Parsed."""
    original = text.strip()
    s = ' ' + original + ' '
    result = Parsed(title=original)
    day = None
    at = None

    # --- priority marks: !!! urgent, !! high, ! (alone) medium ---
    m = re.search(r'(?<!\S)(!{1,3})(?!\S)', s)
    if m:
        result.priority = {1: 'medium', 2: 'high', 3: 'urgent'}[len(m.group(1))]
        s = _cut(s, m)
    m = re.search(r'(?i)(?<!\S)(asap|urgent(?:ly)?)(?!\S)', s)
    if m and not result.priority:
        result.priority = 'urgent'
        if m.group(1).lower() == 'asap':
            s = _cut(s, m)

    # --- repeats ---
    repeat_patterns = [
        (r'(?i)\b(every\s*day|daily|everyday)\b', 'daily'),
        (r'(?i)\b(every\s*week|weekly)\b', 'weekly'),
        (r'(?i)\b(every\s*(?:2|two)\s*weeks|fortnightly|biweekly)\b', 'biweekly'),
        (r'(?i)\b(every\s*month|monthly)\b', 'monthly'),
        (r'(?i)\b(every\s*year|yearly|annually)\b', 'yearly'),
    ]
    for pattern, freq in repeat_patterns:
        m = re.search(pattern, s)
        if m:
            result.repeat = freq
            s = _cut(s, m)
            break
    if not result.repeat:
        m = re.search(r'(?i)\bevery\s+(' + '|'.join(WEEKDAYS + list(WEEKDAY_SHORT)) + r')\b', s)
        if m:
            result.repeat = 'weekly'
            day = _next_weekday(now.date(), _weekday_index(m.group(1)))
            s = _cut(s, m)

    # --- "in 30 min", "in 2 hours", "in 3 days" ---
    m = re.search(r'(?i)\bin\s+(\d{1,3}|an?|one|half an)\s*(min(?:ute)?s?|h(?:ou)?rs?|hours?|days?|weeks?)\b', s)
    if m:
        amount_word = m.group(1).lower()
        amount = {'a': 1, 'an': 1, 'one': 1}.get(amount_word)
        unit = m.group(2).lower()
        if amount_word == 'half an':
            delta = timedelta(minutes=30)
        else:
            amount = amount or int(amount_word)
            if unit.startswith('min'):
                delta = timedelta(minutes=amount)
            elif unit.startswith('h'):
                delta = timedelta(hours=amount)
            elif unit.startswith('d'):
                delta = timedelta(days=amount)
            else:
                delta = timedelta(weeks=amount)
        due = now + delta
        if delta < timedelta(days=1):
            result.has_time = True
            result.due = due.replace(second=0, microsecond=0)
        else:
            day = due.date()
        s = _cut(s, m)

    # --- day words ---
    if result.due is None and day is None:
        m = re.search(r'(?i)\b(?:by\s+|on\s+|due\s+)?(today|tonight|this\s+(?:morning|afternoon|evening))\b', s)
        if m:
            day = now.date()
            word = m.group(1).lower()
            if word == 'tonight':
                at = PARTS_OF_DAY['tonight']
            elif word.startswith('this'):
                at = PARTS_OF_DAY[word.split()[-1]]
            s = _cut(s, m)
    if result.due is None and day is None:
        m = re.search(r'(?i)\b(?:by\s+|on\s+|due\s+)?(tomorrow|tmrw|tmr|tomorow)(?:\s+(morning|afternoon|evening|night))?\b', s)
        if m:
            day = now.date() + timedelta(days=1)
            if m.group(2):
                at = PARTS_OF_DAY[m.group(2).lower()]
            s = _cut(s, m)
    if result.due is None and day is None:
        m = re.search(r'(?i)\bnext\s+week\b', s)
        if m:
            day = _next_weekday(now.date(), 0, force_next=True)
            s = _cut(s, m)
    if result.due is None and day is None:
        names = '|'.join(WEEKDAYS + list(WEEKDAY_SHORT))
        m = re.search(r'(?i)\b(?:by\s+|on\s+|due\s+)?(next\s+)?(' + names + r')\b', s)
        if m:
            day = _next_weekday(now.date(), _weekday_index(m.group(2)), force_next=bool(m.group(1)))
            s = _cut(s, m)
    if result.due is None and day is None:
        months = '|'.join(sorted(MONTHS, key=len, reverse=True))
        m = (re.search(r'(?i)\b(?:on\s+|by\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(' + months + r')\b', s)
             or re.search(r'(?i)\b(?:on\s+|by\s+)?(' + months + r')\s+(\d{1,2})(?:st|nd|rd|th)?\b', s))
        if m:
            a, b = m.group(1), m.group(2)
            day_num, month = (int(a), MONTHS[b.lower()]) if a.isdigit() else (int(b), MONTHS[a.lower()])
            try:
                candidate = now.date().replace(month=month, day=day_num)
                if candidate < now.date():
                    candidate = candidate.replace(year=candidate.year + 1)
                day = candidate
                s = _cut(s, m)
            except ValueError:
                pass

    # --- time of day: "at 7pm", "7:30 pm", "19:00", "at 7", "noon" ---
    if result.due is None:
        m = re.search(r'(?i)\b(?:at\s+|@\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)(?!\w)', s)
        if m:
            hour = int(m.group(1)) % 12
            minute = int(m.group(2) or 0)
            if m.group(3).lower().startswith('p'):
                hour += 12
            if minute < 60:
                at = time(hour, minute)
                s = _cut(s, m)
        else:
            m = re.search(r'(?i)\b(?:at\s+|@\s*)?([01]?\d|2[0-3]):([0-5]\d)\b', s)
            if m:
                at = time(int(m.group(1)), int(m.group(2)))
                s = _cut(s, m)
            else:
                m = re.search(r'(?i)\bat\s+(\d{1,2})(?![\w%:])', s)
                if m and 1 <= int(m.group(1)) <= 12:
                    hour = int(m.group(1))
                    # "at 7" with no am/pm: 1-7 is almost always afternoon/evening
                    if hour < 8:
                        hour += 12
                    at = time(hour, 0)
                    s = _cut(s, m)
                else:
                    m = re.search(r'(?i)\b(?:at\s+|in\s+the\s+)?(noon|midday|midnight|morning|afternoon|evening)\b', s)
                    if m and (day is not None or m.group(1).lower() in ('noon', 'midday', 'midnight')):
                        at = PARTS_OF_DAY[m.group(1).lower()]
                        s = _cut(s, m)

    # --- build the due date ---
    if result.due is None and (day is not None or at is not None):
        tz = now.tzinfo
        if day is None:
            day = now.date()
            if datetime.combine(day, at, tz) <= now:
                day += timedelta(days=1)
        if at is None:
            if day == now.date():
                # "today" with no time: 5 PM, or an hour from now if that's passed
                at = time(17, 0)
                if datetime.combine(day, at, tz) <= now:
                    later = now + timedelta(hours=1)
                    at = time(later.hour, (later.minute // 5) * 5)
                    if later.date() != day:
                        day = later.date()
            else:
                at = DEFAULT_TIME
        else:
            result.has_time = True
        result.due = datetime.combine(day, at, tz)

    # A repeat needs a start date
    if result.repeat and result.due is None:
        start = now + timedelta(days=1)
        result.due = datetime.combine(start.date(), DEFAULT_TIME, now.tzinfo)

    title = re.sub(r'\s{2,}', ' ', s).strip(' ,.-')
    # Dangling little words left behind ("Call mum at", "Submit by")
    title = re.sub(r'(?i)\s+(at|on|by|due|in|for|this|next|every)$', '', title).strip(' ,.-')
    result.title = title or original
    return result
