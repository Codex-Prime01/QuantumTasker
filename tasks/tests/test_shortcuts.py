"""Tests for "Hey Siri, add to Quantum": personal keys and the add-by-text endpoint."""
import json
import re
import zoneinfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tasks.models import Task, UserProfile


class ShortcutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.timezone = 'Africa/Lagos'
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')

    def make_key(self):
        page = self.client.post(reverse('userp_settings'), {'form_type': 'shortcut_create'})
        match = re.search(r'value="(qm_[^"]+)"', page.content.decode())
        self.assertIsNotNone(match, 'the new key should be shown once on the page')
        return match.group(1)

    def add(self, key, text):
        return self.client.post(reverse('shortcut_add'), data=json.dumps({'text': text}),
                                content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {key}')

    def test_key_is_shown_once_and_only_a_hash_is_stored(self):
        key = self.make_key()
        stored = UserProfile.objects.get(user=self.user).shortcut_key_hash
        self.assertEqual(len(stored), 64)
        self.assertNotIn(key, stored)
        later = self.client.get(reverse('userp_settings') + '?tab=shortcuts')
        self.assertNotContains(later, key)
        self.assertContains(later, 'Key is set up')

    def test_siri_adds_a_task_with_time_and_reply(self):
        key = self.make_key()
        self.client.logout()  # Shortcuts has no session, only the key
        res = self.add(key, 'Pay rent tomorrow 6pm !!')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('Pay rent', data['message'])
        task = Task.objects.get(id=data['id'])
        self.assertEqual(task.user, self.user)
        self.assertEqual(task.priority, 'high')
        # "6pm" means 6pm where the user lives (their saved timezone), not the server's
        local = task.due_date.astimezone(zoneinfo.ZoneInfo('Africa/Lagos'))
        self.assertEqual((local.hour, local.minute), (18, 0))

    def test_bad_or_missing_key_is_refused(self):
        self.client.logout()
        self.assertEqual(self.add('qm_wrong', 'Hack').status_code, 401)
        self.assertEqual(self.add('', 'Hack').status_code, 401)
        res = self.client.post(reverse('shortcut_add'), {'text': 'No header'})
        self.assertEqual(res.status_code, 401)
        self.assertFalse(Task.objects.exists())

    def test_revoked_key_stops_working(self):
        key = self.make_key()
        self.client.post(reverse('userp_settings'), {'form_type': 'shortcut_revoke'})
        self.client.logout()
        self.assertEqual(self.add(key, 'Too late').status_code, 401)

    def test_new_key_replaces_old_one(self):
        old = self.make_key()
        new = self.make_key()
        self.client.logout()
        self.assertEqual(self.add(old, 'Old').status_code, 401)
        self.assertEqual(self.add(new, 'New').status_code, 200)

    def test_empty_text(self):
        key = self.make_key()
        self.assertEqual(self.add(key, '   ').status_code, 400)

    def test_only_post(self):
        self.assertEqual(self.client.get(reverse('shortcut_add')).status_code, 405)
