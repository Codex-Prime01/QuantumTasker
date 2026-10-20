"""
The list of built-in alarm sounds. One place to add or rename a sound:
the task form, Settings, the dropdown and the alarm player all read it.

The mp3 files live in tasks/static/tasks/tones/ and are made by
`python manage.py make_tones`.
"""
from django.templatetags.static import static

DEFAULT_TONE = 'classic'

# (group, [(id, name, short description), ...])
TONE_GROUPS = [
    ('Gentle', [
        ('sunrise', 'Sunrise', 'Warm pad with a rising arpeggio'),
        ('chime', 'Soft chime', 'Three soft bell notes'),
        ('marimba', 'Marimba', 'Bouncy wooden melody'),
        ('harp', 'Harp', 'Sparkly plucked strings'),
        ('musicbox', 'Music box', 'Tiny lullaby tune'),
        ('rise', 'Slow rise', 'Starts quiet, gets busier'),
    ]),
    ('Modern', [
        ('sonar', 'Sonar', 'Clean ping, ping'),
        ('crystal', 'Crystal', 'Bright glassy notes'),
        ('pulse', 'Pulse', 'Beat with a little bass'),
        ('synthwave', 'Synthwave', 'Retro 80s chords'),
        ('arcade', 'Arcade', 'Game level-up jingle'),
        ('bubbles', 'Bubbles', 'Playful pops'),
    ]),
    ('Classic', [
        ('classic', 'Classic', 'Beep beep beep beep'),
        ('digital', 'Digital watch', 'Sharp double beep'),
        ('bell', 'Old bell', 'Ringing desk-clock bell'),
    ]),
    ('Loud', [
        ('urgent', 'Urgent', 'Fast two-tone alert'),
        ('siren', 'Siren', 'Rising and falling wail'),
        ('buzzer', 'Buzzer', 'Game-show buzz'),
        ('klaxon', 'Klaxon', 'Hard to sleep through'),
    ]),
]

TONES = {tone_id: {'id': tone_id, 'name': name, 'desc': desc, 'group': group}
         for group, items in TONE_GROUPS for tone_id, name, desc in items}


def tone_choices():
    """Grouped choices for a Django Select: [(group, [(id, name), ...]), ...]."""
    return [(group, [(tone_id, name) for tone_id, name, _ in items]) for group, items in TONE_GROUPS]


def tone_catalog():
    """What the browser needs: id -> {name, desc, group, url}."""
    return {tone_id: {**info, 'url': static(f'tasks/tones/{tone_id}.mp3')} for tone_id, info in TONES.items()}


def is_builtin(tone):
    return tone in TONES
