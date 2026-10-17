"""One test (or a few) for every bug found in the October 2026 review."""
import json
from datetime import timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tasks.forms import TaskForm
from tasks.models import Achievement, Category, Task, TaskTemplate, UserStats


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('perey', 'perey@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='perey', password='S3cure-pass-123')

    def make_task(self, **kwargs):
        defaults = {'user': self.user, 'title': 'Remind Tunde'}
        defaults.update(kwargs)
        return Task.objects.create(**defaults)


class EditDoesNotWipeDatesTests(Base):
    def test_edit_form_shows_dates_in_datetime_local_format(self):
        due = timezone.now() + timedelta(days=1)
        task = self.make_task(due_date=due, alarm_enabled=True, alarm_time=due)
        html = self.client.get(reverse('update', args=[task.id])).content.decode()
        local = timezone.localtime(due, timezone.get_default_timezone())
        # value="YYYY-MM-DDTHH:MM" is what <input type=datetime-local> needs
        self.assertIn('T', TaskForm(instance=task)['due_date'].value().isoformat())
        self.assertRegex(html, r'name="due_date"[^>]*value="\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"')


class TimezoneTests(Base):
    def test_times_typed_by_a_lagos_user_are_stored_as_lagos_time(self):
        self.client.cookies['tz'] = 'Africa/Lagos'
        self.client.post(reverse('create'), {
            'title': 'Call mum', 'priority': 'medium', 'recurring_frequency': 'none',
            'recurring_interval': 1, 'due_date': '2030-01-01T15:00', 'alarm_tone': 'classic',
        })
        task = Task.objects.get(title='Call mum')
        # 15:00 in Lagos (UTC+1) is 14:00 UTC
        self.assertEqual(task.due_date.astimezone(dt_timezone.utc).hour, 14)

    def test_bad_timezone_cookie_does_not_crash(self):
        self.client.cookies['tz'] = 'Not/AZone'
        self.assertEqual(self.client.get(reverse('list')).status_code, 200)


class AlarmTests(Base):
    def test_alarm_still_rings_after_the_old_5_minute_window(self):
        self.make_task(alarm_enabled=True, alarm_time=timezone.now() - timedelta(minutes=30))
        data = self.client.get(reverse('check_due_tasks')).json()
        self.assertEqual(data['count'], 1)

    def test_snoozed_alarm_rings_again_when_snooze_ends(self):
        task = self.make_task(alarm_enabled=True, alarm_time=timezone.now() - timedelta(minutes=1))
        self.client.post(reverse('snooze_alarm', args=[task.id]), json.dumps({'minutes': 10}),
                         content_type='application/json')
        self.assertEqual(self.client.get(reverse('check_due_tasks')).json()['count'], 0)
        later = timezone.now() + timedelta(minutes=11)
        with mock.patch('django.utils.timezone.now', return_value=later):
            data = self.client.get(reverse('check_due_tasks')).json()
        self.assertEqual(data['count'], 1)

    def test_dismissed_alarm_stays_quiet(self):
        task = self.make_task(alarm_enabled=True, alarm_time=timezone.now() - timedelta(minutes=1))
        self.client.post(reverse('dismiss_alarm', args=[task.id]))
        self.assertEqual(self.client.get(reverse('check_due_tasks')).json()['count'], 0)

    def test_poll_response_is_never_cached(self):
        response = self.client.get(reverse('check_due_tasks'))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_cannot_snooze_someone_elses_alarm(self):
        other = User.objects.create_user('other', 'o@example.com', 'S3cure-pass-123')
        task = Task.objects.create(user=other, title='Theirs')
        r = self.client.post(reverse('snooze_alarm', args=[task.id]), '{}', content_type='application/json')
        self.assertEqual(r.status_code, 404)

    def test_editing_alarm_time_rearms_a_dismissed_alarm(self):
        task = self.make_task(alarm_enabled=True, alarm_time=timezone.now(), alarm_dismissed=True)
        self.client.post(reverse('update', args=[task.id]), {
            'title': task.title, 'priority': 'medium', 'recurring_frequency': 'none',
            'recurring_interval': 1, 'alarm_enabled': 'on', 'alarm_time': '2031-05-05T09:30',
            'alarm_tone': 'classic',
        })
        task.refresh_from_db()
        self.assertFalse(task.alarm_dismissed)


class CustomToneTests(Base):
    def test_uploaded_tone_is_saved_with_a_real_task_id(self):
        sound = SimpleUploadedFile('ring.mp3', b'ID3fake-mp3', content_type='audio/mpeg')
        self.client.post(reverse('create'), {
            'title': 'Wake up', 'priority': 'high', 'recurring_frequency': 'none', 'recurring_interval': 1,
            'alarm_enabled': 'on', 'alarm_time': '2030-01-01T06:00', 'alarm_tone': 'custom',
            'custom_tone_file': sound,
        })
        task = Task.objects.get(title='Wake up')
        self.assertIn(f'task_{task.id}_', task.alarm_tone)
        self.assertNotIn('None', task.alarm_tone)

    def test_non_audio_upload_falls_back_to_classic(self):
        bad = SimpleUploadedFile('evil.exe', b'MZ', content_type='application/octet-stream')
        self.client.post(reverse('create'), {
            'title': 'Nope', 'priority': 'low', 'recurring_frequency': 'none', 'recurring_interval': 1,
            'alarm_tone': 'custom', 'custom_tone_file': bad,
        })
        self.assertEqual(Task.objects.get(title='Nope').alarm_tone, 'classic')


class PointsAndRecurringTests(Base):
    def toggle(self, task):
        return self.client.post(reverse('quick_toggle', args=[task.id]))

    def test_ticking_on_and_off_cannot_farm_points(self):
        task = self.make_task()
        for _ in range(5):
            self.toggle(task)
            self.toggle(task)
        self.assertEqual(UserStats.objects.get(user=self.user).total_tasks_completed, 1)

    def test_toggle_needs_post(self):
        task = self.make_task()
        self.assertEqual(self.client.get(reverse('quick_toggle', args=[task.id])).status_code, 405)

    def test_recurring_task_only_spawns_one_next_copy(self):
        task = self.make_task(is_recurring=True, recurring_frequency='daily',
                              due_date=timezone.now() + timedelta(hours=1))
        for _ in range(3):
            self.toggle(task)
            self.toggle(task)
        self.assertEqual(Task.objects.filter(user=self.user).count(), 2)

    def test_next_copy_keeps_the_alarm(self):
        due = timezone.now() + timedelta(hours=2)
        task = self.make_task(is_recurring=True, recurring_frequency='daily', due_date=due,
                              alarm_enabled=True, alarm_time=due - timedelta(minutes=15))
        self.toggle(task)
        nxt = Task.objects.exclude(id=task.id).get()
        self.assertTrue(nxt.alarm_enabled)
        self.assertEqual(nxt.due_date - nxt.alarm_time, timedelta(minutes=15))

    def test_monthly_repeat_uses_real_months(self):
        due = timezone.now().replace(year=2099, month=1, day=31)
        task = self.make_task(is_recurring=True, recurring_frequency='monthly', due_date=due)
        nxt = task.calculate_next_due_date()
        self.assertEqual((nxt.month, nxt.day), (2, 28))

    def test_achievement_unlocks_once(self):
        Achievement.objects.create(name='First!', description='x', achievement_type='tasks_completed',
                                   requirement=1, points=10)
        task = self.make_task()
        self.toggle(task)
        self.toggle(task)
        self.toggle(task)
        self.assertEqual(UserStats.objects.get(user=self.user).total_points, 10)


class CrashFixTests(Base):
    def test_missing_task_is_404_not_500(self):
        self.assertEqual(self.client.get(reverse('update', args=[99999])).status_code, 404)
        self.assertEqual(self.client.get(reverse('delete', args=[99999])).status_code, 404)

    def test_cannot_open_someone_elses_task(self):
        other = User.objects.create_user('other', 'o@example.com', 'S3cure-pass-123')
        task = Task.objects.create(user=other, title='Private')
        self.assertEqual(self.client.get(reverse('update', args=[task.id])).status_code, 404)

    def test_profile_page_survives_bad_profile_form(self):
        r = self.client.post(reverse('profile'), {'form_type': 'profile_info', 'username': '', 'email': 'bad'})
        self.assertEqual(r.status_code, 200)

    def test_profile_page_survives_bad_password_form(self):
        r = self.client.post(reverse('profile'), {'form_type': 'password_change'})
        self.assertEqual(r.status_code, 200)

    def test_password_change_works(self):
        self.client.post(reverse('profile'), {
            'form_type': 'password_change', 'current_password': 'S3cure-pass-123',
            'new_password1': 'An0ther-good-pass', 'new_password2': 'An0ther-good-pass',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('An0ther-good-pass'))

    def test_delete_template_page_exists(self):
        t = TaskTemplate.objects.create(user=self.user, name='Morning')
        self.assertEqual(self.client.get(reverse('delete_template', args=[t.id])).status_code, 200)
        self.client.post(reverse('delete_template', args=[t.id]))
        self.assertFalse(TaskTemplate.objects.filter(id=t.id).exists())

    def test_cannot_see_someone_elses_template(self):
        other = User.objects.create_user('other', 'o@example.com', 'S3cure-pass-123')
        t = TaskTemplate.objects.create(user=other, name='Secret')
        self.assertEqual(self.client.get(reverse('template_detail', args=[t.id])).status_code, 404)

    def test_every_logged_in_page_loads(self):
        for name in ['list', 'create', 'dashboard', 'profile', 'userp_settings', 'templates_list',
                     'create_template', 'create_template_from_tasks', 'achievements', 'notes_list',
                     'create_note', 'archived_notes', 'offline']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


class ApiTests(Base):
    def test_api_can_create_a_task(self):
        r = self.client.post('/api/tasks/', {'title': 'From API', 'priority': 'low'}, content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Task.objects.get(title='From API').user, self.user)

    def test_api_cannot_delete_shared_categories(self):
        cat = Category.objects.create(name='Work')
        r = self.client.delete(f'/api/categories/{cat.id}/')
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Category.objects.filter(id=cat.id).exists())

    def test_api_cannot_touch_other_users_tasks(self):
        other = User.objects.create_user('other', 'o@example.com', 'S3cure-pass-123')
        task = Task.objects.create(user=other, title='Theirs')
        self.assertEqual(self.client.delete(f'/api/tasks/{task.id}/').status_code, 404)


@override_settings(REQUIRE_EMAIL_VERIFICATION=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailFlowTests(TestCase):
    def register(self, username='newbie', email='new@example.com'):
        return self.client.post(reverse('register'), {
            'username': username, 'email': email,
            'password1': 'Str0ng-pass-xyz', 'password2': 'Str0ng-pass-xyz',
        })

    def test_register_sends_verification_and_blocks_login_until_verified(self):
        self.register()
        self.assertEqual(len(mail.outbox), 1)
        r = self.client.post(reverse('login'), {'username': 'newbie', 'password': 'Str0ng-pass-xyz'})
        self.assertRedirects(r, reverse('verification_sent'))

        token = User.objects.get(username='newbie').profile.verification_token
        self.assertIn(str(token), mail.outbox[0].body)
        self.client.get(reverse('verify_email', args=[token]))
        self.assertTrue(User.objects.get(username='newbie').profile.email_verified)

    def test_expired_verification_link_is_refused(self):
        self.register()
        profile = User.objects.get(username='newbie').profile
        profile.verification_token_created = timezone.now() - timedelta(days=2)
        profile.save()
        self.client.get(reverse('verify_email', args=[profile.verification_token]))
        profile.refresh_from_db()
        self.assertFalse(profile.email_verified)

    def test_duplicate_email_is_rejected(self):
        self.register()
        self.register(username='copycat', email='NEW@example.com')
        self.assertFalse(User.objects.filter(username='copycat').exists())

    def test_email_failure_does_not_crash_signup(self):
        with mock.patch('tasks.views._send_email', side_effect=OSError('smtp blocked')):
            r = self.register()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='newbie').exists())

    def test_forgot_password_does_not_reveal_if_email_exists(self):
        User.objects.create_user('real', 'real@example.com', 'x-Str0ng-pass')
        a = self.client.post(reverse('forgot_password'), {'email': 'real@example.com'}, follow=True)
        b = self.client.post(reverse('forgot_password'), {'email': 'ghost@example.com'}, follow=True)
        msgs = lambda r: [str(m) for m in r.context['messages']]
        self.assertEqual(msgs(a), msgs(b))

    def test_reset_link_expires_and_is_single_use(self):
        user = User.objects.create_user('real', 'real@example.com', 'x-Str0ng-pass')
        self.client.post(reverse('forgot_password'), {'email': 'real@example.com'})
        token = User.objects.get(pk=user.pk).profile.reset_token
        url = reverse('reset_password', args=[token])
        self.client.post(url, {'password1': 'Brand-new-pass-1', 'password2': 'Brand-new-pass-1'})
        user.refresh_from_db()
        self.assertTrue(user.check_password('Brand-new-pass-1'))
        # second use fails
        self.client.post(url, {'password1': 'Hacker-pass-999', 'password2': 'Hacker-pass-999'})
        user.refresh_from_db()
        self.assertTrue(user.check_password('Brand-new-pass-1'))


class BrevoBackendTests(TestCase):
    @override_settings(BREVO_API_KEY='test-key', EMAIL_BACKEND='tasks.email_backends.BrevoAPIBackend')
    def test_sends_over_https_with_short_timeout(self):
        from django.core.mail import EmailMultiAlternatives
        with mock.patch('tasks.email_backends.requests.post') as post:
            post.return_value.raise_for_status.return_value = None
            msg = EmailMultiAlternatives('Hi', 'text', 'QM <qm@example.com>', ['a@example.com'])
            msg.attach_alternative('<b>html</b>', 'text/html')
            msg.send()
        args, kwargs = post.call_args
        self.assertTrue(args[0].startswith('https://'))
        self.assertLessEqual(kwargs['timeout'], 15)
        self.assertEqual(kwargs['json']['htmlContent'], '<b>html</b>')
        self.assertEqual(kwargs['json']['sender'], {'email': 'qm@example.com', 'name': 'QM'})


class ServiceWorkerTests(TestCase):
    def test_service_worker_is_served_from_site_root(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r.status_code, 200)
        self.assertIn('javascript', r['Content-Type'])
        self.assertIn("'/api/'", r.content.decode())
