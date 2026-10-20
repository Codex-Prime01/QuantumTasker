"""
Builds the built-in alarm sounds in tasks/static/tasks/tones/.

Every sound is made from scratch with maths (no samples), so it is
original and free to use. Run it again after changing a recipe:

    python manage.py make_tones

It needs numpy and ffmpeg. These are only needed on your own computer;
the finished .mp3 files are committed, so Render doesn't need either.
"""
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

SR = 44100
OUT = Path(__file__).resolve().parents[2] / 'static' / 'tasks' / 'tones'


def _np():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise CommandError('pip install numpy first') from exc
    return np


# ---------------------------------------------------------------------------
# Small synth toolkit
# ---------------------------------------------------------------------------
def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


class Track:
    def __init__(self, seconds):
        np = _np()
        self.np = np
        self.buf = np.zeros(int(SR * seconds))

    def add(self, sig, at):
        i = int(at * SR)
        end = min(len(self.buf), i + len(sig))
        if i < end:
            self.buf[i:end] += sig[: end - i]

    def t(self, dur):
        return self.np.arange(int(SR * dur)) / SR


def env(np, n, attack=0.005, decay=0.4, sustain=0.0, release=0.05):
    """Attack, then exponential decay towards the sustain level, then release."""
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = sustain + (1 - sustain) * np.exp(-np.maximum(t - attack, 0) / max(decay, 1e-4))
    e = a * d
    r = int(release * SR)
    if r and r < n:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def tone(tr, freq, dur, shape='sine', decay=0.4, attack=0.005, sustain=0.0, vol=1.0, partials=None):
    np = tr.np
    t = tr.t(dur)
    if partials is None:
        partials = {'sine': [(1, 1)],
                    'soft': [(1, 1), (2, 0.25), (3, 0.08)],
                    'square': [(k, 1 / k) for k in range(1, 16, 2)],
                    'saw': [(k, 1 / k) for k in range(1, 14)],
                    'bell': [(1, 1), (2.76, 0.45), (5.4, 0.25), (8.93, 0.12)],
                    'marimba': [(1, 1), (3.93, 0.3), (9.2, 0.08)]}[shape]
    sig = np.zeros_like(t)
    for mult, amp in partials:
        f = freq * mult
        if f > SR / 2.2:
            continue
        # higher partials die faster: sounds more natural
        p_decay = decay / (1 + 0.6 * (mult - 1)) if shape in ('bell', 'marimba', 'soft') else decay
        sig += amp * np.sin(2 * np.pi * f * t) * env(np, len(t), attack, p_decay, sustain)
    return sig * vol


def sweep(tr, f0, f1, dur, vol=1.0, shape='sine', curve='lin'):
    np = tr.np
    t = tr.t(dur)
    if curve == 'exp':
        f = f0 * (f1 / f0) ** (t / dur)
    else:
        f = f0 + (f1 - f0) * t / dur
    phase = 2 * np.pi * np.cumsum(f) / SR
    if shape == 'square':
        sig = np.tanh(4 * np.sin(phase)) * 0.6
    elif shape == 'saw':
        sig = sum(np.sin(k * phase) / k for k in range(1, 10)) * 0.6
    else:
        sig = np.sin(phase)
    return sig * env(np, len(t), 0.01, 10, 1.0, 0.03) * vol


def pluck(tr, freq, dur, vol=1.0, bright=0.5):
    """Karplus-Strong string pluck (harp / guitar-ish)."""
    np = tr.np
    n = int(SR * dur)
    period = int(SR / freq)
    rng = np.random.default_rng(int(freq * 100))
    buf = rng.uniform(-1, 1, period)
    out = np.zeros(n)
    blend = 0.5 + bright * 0.49
    for i in range(n):
        out[i] = buf[i % period]
        nxt = buf[(i + 1) % period]
        buf[i % period] = 0.996 * (blend * buf[i % period] + (1 - blend) * nxt)
    return out * vol


def reverb(np, x, mix=0.25, room=0.6):
    """Cheap but pleasant: a few feedback delays (Schroeder-style)."""
    out = np.zeros(len(x))
    for ms, g in ((29.7, room), (37.1, room * 0.95), (41.1, room * 0.9), (43.7, room * 0.85)):
        d = int(SR * ms / 1000)
        y = x.copy()
        for i in range(d, len(y)):
            y[i] += g * y[i - d]
        out += y
    out /= 4
    return (1 - mix) * x + mix * out / (np.max(np.abs(out)) + 1e-9) * np.max(np.abs(x))


def lowpass(np, x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    prev = 0.0
    for i, v in enumerate(x):
        prev = (1 - a) * v + a * prev
        y[i] = prev
    return y


# ---------------------------------------------------------------------------
# Recipes. Each returns a numpy array. Keep them 6-10 s so they loop well.
# ---------------------------------------------------------------------------
def r_classic(tr):
    for rep in range(4):
        base = rep * 2.0
        for k in range(4):
            tr.add(tone(tr, 1000, 0.09, 'soft', decay=5, sustain=1, vol=0.7), base + k * 0.16)
    return tr.buf


def r_digital(tr):
    for rep in range(6):
        for k in range(2):
            tr.add(tone(tr, 2093, 0.07, 'square', decay=5, sustain=1, vol=0.35), rep * 1.2 + k * 0.13)
            tr.add(tone(tr, 2637, 0.07, 'square', decay=5, sustain=1, vol=0.25), rep * 1.2 + k * 0.13 + 0.035)
    return tr.buf


def r_bell(tr):
    for rep in range(4):
        b = rep * 2.0
        for k in range(10):
            tr.add(tone(tr, 1318 if k % 2 else 1175, 0.6, 'bell', decay=0.25, vol=0.45), b + k * 0.06)
    return tr.buf


def r_chime(tr):
    notes = [76, 79, 84]
    for rep in range(3):
        for k, n in enumerate(notes):
            tr.add(tone(tr, midi(n), 2.2, 'bell', decay=0.9, vol=0.5), rep * 2.6 + k * 0.28)
    return tr.buf


def r_sunrise(tr):
    # Slow rising arpeggio over a warm pad
    chord = [60, 64, 67, 71, 74, 76, 79, 83]
    for rep in range(2):
        b = rep * 4.0
        tr.add(tone(tr, midi(48), 4.0, 'soft', attack=0.8, decay=4, sustain=0.6, vol=0.25), b)
        tr.add(tone(tr, midi(55), 4.0, 'soft', attack=0.8, decay=4, sustain=0.6, vol=0.18), b)
        for k, n in enumerate(chord):
            tr.add(tone(tr, midi(n), 1.6, 'soft', attack=0.01, decay=0.6, vol=0.32), b + k * 0.22)
    return tr.buf


def r_marimba(tr):
    melody = [(72, 0), (76, .2), (79, .4), (76, .6), (81, .8), (79, 1.2), (76, 1.4), (72, 1.6)]
    for rep in range(3):
        for n, at in melody:
            tr.add(tone(tr, midi(n), 0.7, 'marimba', decay=0.18, vol=0.6), rep * 2.4 + at)
            tr.add(tone(tr, midi(n - 12), 0.7, 'marimba', decay=0.2, vol=0.2), rep * 2.4 + at)
    return tr.buf


def r_harp(tr):
    up = [60, 64, 67, 72, 76, 79, 84, 88]
    for rep in range(3):
        for k, n in enumerate(up):
            tr.add(pluck(tr, midi(n), 1.6, vol=0.5, bright=0.7), rep * 2.5 + k * 0.08)
    return tr.buf


def r_musicbox(tr):
    melody = [84, 88, 91, 88, 86, 89, 93, 89, 84, 88, 91, 96]
    for rep in range(2):
        for k, n in enumerate(melody):
            tr.add(tone(tr, midi(n), 1.2, 'bell', decay=0.5, vol=0.35, partials=[(1, 1), (3, 0.15), (5.1, 0.05)]),
                   rep * 3.6 + k * 0.25)
    return tr.buf


def r_sonar(tr):
    for rep in range(4):
        b = rep * 2.0
        tr.add(tone(tr, 1568, 1.2, 'sine', decay=0.35, vol=0.6), b)
        tr.add(tone(tr, 2093, 1.0, 'sine', decay=0.3, vol=0.4), b + 0.18)
        tr.add(tone(tr, 1568, 0.8, 'sine', decay=0.2, vol=0.25), b + 0.5)
    return tr.buf


def r_pulse(tr):
    for beat in range(32):
        at = beat * 0.25
        n = [69, 69, 76, 69, 72, 69, 76, 74][beat % 8]
        tr.add(tone(tr, midi(n), 0.2, 'square', decay=0.09, vol=0.6), at)
        if beat % 4 == 0:
            tr.add(sweep(tr, 140, 45, 0.18, vol=0.8, curve='exp') * env(tr.np, int(.18 * SR), 0.001, 0.06), at)
    return tr.buf


def r_crystal(tr):
    notes = [88, 91, 95, 100, 95, 91]
    for rep in range(3):
        for k, n in enumerate(notes):
            tr.add(tone(tr, midi(n), 1.4, 'bell', decay=0.45, vol=0.3,
                        partials=[(1, 1), (2.01, 0.4), (4.2, 0.15)]), rep * 2.4 + k * 0.12)
    return tr.buf


def r_arcade(tr):
    seq = [72, 76, 79, 84, 79, 76, 72, 76, 79, 84, 88, 91]
    for rep in range(3):
        for k, n in enumerate(seq):
            tr.add(tone(tr, midi(n), 0.09, 'square', decay=5, sustain=1, vol=0.25), rep * 2.4 + k * 0.1)
        tr.add(sweep(tr, 600, 1800, 0.25, vol=0.2, shape='square', curve='exp'), rep * 2.4 + 1.3)
    return tr.buf


def r_synthwave(tr):
    np = tr.np
    chords = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]]
    for i, ch in enumerate(chords):
        b = i * 2.0
        pad = sum(tone(tr, midi(n), 2.0, 'saw', attack=0.05, decay=3, sustain=0.7, vol=0.12) for n in ch)
        tr.add(lowpass(np, pad, 1800), b)
        for k in range(8):
            n = ch[k % 3] + 12 * (1 + (k // 3) % 2)
            tr.add(tone(tr, midi(n), 0.2, 'square', decay=0.08, vol=0.14), b + k * 0.25)
        tr.add(tone(tr, midi(ch[0] - 24), 2.0, 'soft', decay=0.5, vol=0.5), b)
    return tr.buf


def r_bubbles(tr):
    rng = tr.np.random.default_rng(7)
    for k in range(40):
        f0 = rng.uniform(300, 700)
        tr.add(sweep(tr, f0, f0 * 2.6, 0.09, vol=0.35, curve='exp') * env(tr.np, int(.09 * SR), 0.002, 0.04), k * 0.2 + rng.uniform(0, 0.08))
    return tr.buf


def r_rise(tr):
    # Gets busier every bar: a gentle wake-up that won't let you sleep
    for bar in range(4):
        b = bar * 2.0
        count = 2 + bar * 2
        for k in range(count):
            n = [72, 79, 76, 84, 79, 88, 84, 91][k % 8]
            tr.add(tone(tr, midi(n), 0.6, 'marimba', decay=0.2, vol=0.3 + 0.12 * bar), b + k * (2.0 / count))
    return tr.buf


def r_urgent(tr):
    for rep in range(16):
        tr.add(tone(tr, 880 if rep % 2 == 0 else 1175, 0.18, 'square', decay=5, sustain=1, vol=0.35), rep * 0.25)
    for rep in range(16):
        tr.add(tone(tr, 880 if rep % 2 == 0 else 1175, 0.18, 'square', decay=5, sustain=1, vol=0.35), 4.2 + rep * 0.25)
    return tr.buf


def r_siren(tr):
    for k in range(4):
        tr.add(sweep(tr, 650, 1300, 1.0, vol=0.5), k * 2.0)
        tr.add(sweep(tr, 1300, 650, 1.0, vol=0.5), k * 2.0 + 1.0)
    return tr.buf


def r_buzzer(tr):
    for k in range(10):
        sig = tone(tr, 220, 0.45, 'saw', decay=5, sustain=1, vol=0.3) + tone(tr, 223, 0.45, 'square', decay=5, sustain=1, vol=0.25)
        tr.add(sig, k * 0.75)
    return tr.buf


def r_klaxon(tr):
    for k in range(5):
        tr.add(sweep(tr, 330, 520, 0.55, vol=0.45, shape='saw') + sweep(tr, 333, 524, 0.55, vol=0.3, shape='square'), k * 1.5)
    return tr.buf


# id, file recipe, seconds, reverb mix
RECIPES = [
    ('classic', r_classic, 8, 0.05), ('digital', r_digital, 7.2, 0.05), ('bell', r_bell, 8, 0.2),
    ('chime', r_chime, 7.8, 0.35), ('sunrise', r_sunrise, 8, 0.35), ('marimba', r_marimba, 7.2, 0.25),
    ('harp', r_harp, 7.5, 0.3), ('musicbox', r_musicbox, 7.2, 0.35), ('rise', r_rise, 8, 0.2),
    ('sonar', r_sonar, 8, 0.35), ('pulse', r_pulse, 8, 0.15), ('crystal', r_crystal, 7.2, 0.4),
    ('arcade', r_arcade, 7.2, 0.1), ('synthwave', r_synthwave, 8, 0.25), ('bubbles', r_bubbles, 8, 0.2),
    ('urgent', r_urgent, 8.4, 0.05), ('siren', r_siren, 8, 0.1), ('buzzer', r_buzzer, 7.5, 0.05),
    ('klaxon', r_klaxon, 7.5, 0.1),
]


class Command(BaseCommand):
    help = 'Generate the built-in alarm sounds (mp3) into tasks/static/tasks/tones/'

    def add_arguments(self, parser):
        parser.add_argument('ids', nargs='*', help='Only build these tones')

    def handle(self, *args, **opts):
        np = _np()
        if not shutil.which('ffmpeg'):
            raise CommandError('ffmpeg is needed to make mp3 files')
        OUT.mkdir(parents=True, exist_ok=True)
        wanted = set(opts['ids'])
        for tone_id, recipe, seconds, mix in RECIPES:
            if wanted and tone_id not in wanted:
                continue
            sig = recipe(Track(seconds))
            if mix:
                sig = reverb(np, sig, mix=mix)
            # tiny fades so the loop point never clicks
            f = int(0.01 * SR)
            sig[:f] *= np.linspace(0, 1, f)
            sig[-f:] *= np.linspace(1, 0, f)
            sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.89
            pcm = (sig * 32767).astype('<i2').tobytes()
            with tempfile.TemporaryDirectory() as tmp:
                wav_path = Path(tmp) / 'x.wav'
                with wave.open(str(wav_path), 'wb') as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(SR)
                    w.writeframes(pcm)
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav_path),
                                '-codec:a', 'libmp3lame', '-b:a', '96k', str(OUT / f'{tone_id}.mp3')], check=True)
            self.stdout.write(f'  ✓ {tone_id}.mp3')
        self.stdout.write(self.style.SUCCESS('Done'))
