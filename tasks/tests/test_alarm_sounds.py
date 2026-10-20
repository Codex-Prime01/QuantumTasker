from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from tasks.models import Task
from tasks.tones import TONES, tone_catalog

TONE_DIR = Path(__file__).resolve().parents[1] / 'static' / 'tasks' / 'tones'


class AlarmSoundTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', 'sam@example.com', 'pass12345!')
        self.client.force_login(self.user)

    def _create(self, **extra):
        data = {
            'title': 'Wake up', 'priority': 'medium', 'recurring_frequency': 'none', 'recurring_interval': 1,
            'due_date': '2030-01-01T07:00', 'alarm_enabled': 'on', 'alarm_time': '2030-01-01T06:30',
        }
        data.update(extra)
        return self.client.post(reverse('create'), data)

    def test_every_built_in_sound_has_a_file(self):
        self.assertGreaterEqual(len(TONES), 15)
        for tone_id in TONES:
            path = TONE_DIR / f'{tone_id}.mp3'
            self.assertTrue(path.exists(), f'missing {path.name}')
            self.assertLess(path.stat().st_size, 300 * 1024, f'{path.name} is too big')
        self.assertTrue(tone_catalog()['sunrise']['url'].endswith('tones/sunrise.mp3'))

    def test_new_sound_is_saved(self):
        self._create(alarm_tone='synthwave')
        self.assertEqual(Task.objects.get(title='Wake up').alarm_tone, 'synthwave')

    def test_unknown_sound_falls_back_to_classic(self):
        self._create(alarm_tone='not-a-sound')
        self.assertEqual(Task.objects.get(title='Wake up').alarm_tone, 'classic')

    def test_create_page_has_grouped_dropdown_and_catalog(self):
        html = self.client.get(reverse('create')).content.decode()
        self.assertIn('data-tone-select', html)
        self.assertIn('<optgroup label="Gentle">', html)
        self.assertIn('value="klaxon"', html)
        self.assertIn('id="qm-tones"', html)
        self.assertIn('up to 25 MB', html)

    @override_settings(MAX_TONE_UPLOAD_BYTES=25 * 1024 * 1024)
    def test_song_bigger_than_2mb_is_accepted(self):
        song = SimpleUploadedFile('song.mp3', b'\0' * (3 * 1024 * 1024), content_type='audio/mpeg')
        self._create(alarm_tone='custom', custom_tone_file=song)
        tone = Task.objects.get(title='Wake up').alarm_tone
        self.assertTrue(tone.startswith(('/', 'http')), tone)

    @override_settings(CLOUDINARY_URL='cloudinary://k:s@demo')
    def test_cloudinary_upload_uses_video_type(self):
        song = SimpleUploadedFile('song.mp3', b'\0' * 2048, content_type='audio/mpeg')
        fake = {'secure_url': 'https://res.cloudinary.com/demo/video/upload/v1/alarm_tones/1/task_1.mp3'}
        with mock.patch('cloudinary.uploader.upload_large', return_value=fake) as up:
            self._create(alarm_tone='custom', custom_tone_file=song)
        self.assertEqual(up.call_args.kwargs['resource_type'], 'video')
        self.assertEqual(Task.objects.get(title='Wake up').alarm_tone, fake['secure_url'])

    def test_settings_default_sound_accepts_new_tones(self):
        from tasks.forms import TaskDefaultsForm
        form = TaskDefaultsForm(instance=self.user.profile)
        values = [v for _, group in form.fields['default_alarm_tone'].widget.choices for v, _ in group]
        self.assertIn('sunrise', values)
        self.assertIn('urgent', values)
