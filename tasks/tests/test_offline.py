"""Tests for the offline app: replayed changes, share target, badge count, service worker."""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Note, SyncReceipt, Task


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')

    def post_json(self, url, body, op=None):
        headers = {'HTTP_X_QM_OP': op} if op else {}
        return self.client.post(url, data=json.dumps(body), content_type='application/json', **headers)


class ReplayTests(Base):
    def test_same_offline_create_twice_makes_one_task(self):
        data = {'title': 'Buy bread', 'priority': 'medium', 'recurring_frequency': 'none',
                'recurring_interval': 1, 'alarm_tone': 'classic'}
        first = self.client.post(reverse('create'), data, HTTP_X_QM_OP='op-1')
        again = self.client.post(reverse('create'), data, HTTP_X_QM_OP='op-1')
        self.assertEqual(first.status_code, 302)
        self.assertEqual(again.json(), {'success': True, 'duplicate': True})
        self.assertEqual(Task.objects.filter(title='Buy bread').count(), 1)

    def test_offline_quick_add_and_note_are_guarded_too(self):
        self.client.post(reverse('list'), {'title': 'Call mum'}, HTTP_X_QM_OP='op-qa')
        self.client.post(reverse('list'), {'title': 'Call mum'}, HTTP_X_QM_OP='op-qa')
        self.assertEqual(Task.objects.filter(title='Call mum').count(), 1)
        note = {'title': 'Wi-Fi', 'content': 'abc123', 'category': 'personal', 'color': '#FFD700'}
        self.client.post(reverse('create_note'), note, HTTP_X_QM_OP='op-note')
        self.client.post(reverse('create_note'), note, HTTP_X_QM_OP='op-note')
        self.assertEqual(Note.objects.filter(title='Wi-Fi').count(), 1)

    def test_failed_form_is_not_remembered(self):
        # No title: the form comes back with errors, so a fixed retry must still work
        res = self.client.post(reverse('create'), {'title': ''}, HTTP_X_QM_OP='op-bad')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(SyncReceipt.objects.filter(op_id='op-bad').exists())

    def test_ids_are_per_user(self):
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        SyncReceipt.objects.create(user=other, op_id='shared-id')
        self.client.post(reverse('create'), {'title': 'Mine', 'priority': 'low', 'recurring_frequency': 'none',
                                             'recurring_interval': 1, 'alarm_tone': 'classic'},
                         HTTP_X_QM_OP='shared-id')
        self.assertTrue(Task.objects.filter(title='Mine', user=self.user).exists())

    def test_normal_requests_without_an_id_are_untouched(self):
        self.client.post(reverse('list'), {'title': 'One'})
        self.client.post(reverse('list'), {'title': 'One'})
        self.assertEqual(Task.objects.filter(title='One').count(), 2)
        self.assertFalse(SyncReceipt.objects.exists())


class QuickToggleTests(Base):
    def test_explicit_state_is_safe_to_send_twice(self):
        task = Task.objects.create(user=self.user, title='Gym')
        url = reverse('quick_toggle', args=[task.id])
        self.assertTrue(self.post_json(url, {'complete': True}).json()['complete'])
        self.assertTrue(self.post_json(url, {'complete': True}).json()['complete'])
        task.refresh_from_db()
        self.assertTrue(task.complete)
        self.assertEqual(self.user.stats.total_tasks_completed, 1)

    def test_old_style_call_still_flips(self):
        task = Task.objects.create(user=self.user, title='Gym')
        res = self.client.post(reverse('quick_toggle', args=[task.id]))
        self.assertTrue(res.json()['complete'])


class ShareTargetTests(Base):
    def test_shared_text_and_link_open_new_task(self):
        res = self.client.get(reverse('share_target'), {'text': 'Read this article\nIt is good', 'url': 'https://example.com/a'})
        self.assertEqual(res.status_code, 302)
        page = self.client.get(res['Location'])
        self.assertContains(page, 'value="Read this article"')
        self.assertContains(page, 'https://example.com/a')

    def test_needs_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('share_target'), {'text': 'x'}).status_code, 302)


class InstalledAppTests(Base):
    def test_badge_counts_overdue_and_due_today(self):
        now = timezone.now()
        Task.objects.create(user=self.user, title='Late', due_date=now - timedelta(days=2))
        Task.objects.create(user=self.user, title='Now', due_date=now)
        Task.objects.create(user=self.user, title='Later', due_date=now + timedelta(days=3))
        Task.objects.create(user=self.user, title='Done', due_date=now, complete=True)
        res = self.client.get(reverse('alarms'))
        self.assertEqual(res.context['nav_counts']['due'], 2)
        self.assertContains(res, 'data-badge="2"')

    def test_manifest_has_share_target_and_alarms_shortcut(self):
        path = Path(__file__).resolve().parents[1] / 'static' / 'tasks' / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['share_target']['action'], '/share/')
        self.assertIn('/alarms/', [s['url'] for s in manifest['shortcuts']])

    def test_service_worker_loads_outbox(self):
        res = self.client.get('/sw.js')
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('importScripts(', body)
        self.assertIn('outbox.js', body)
        self.assertNotIn('{%', body)
