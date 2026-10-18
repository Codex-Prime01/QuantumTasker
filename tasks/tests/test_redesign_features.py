"""Tests for the redesign release: quick add, push alarms, emails, themes."""
import json
import zoneinfo
from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tasks import notify
from tasks.models import Note, PushSubscription, Task, TaskTemplate, TemplateItem
from tasks.nlp import parse

LAGOS = zoneinfo.ZoneInfo('Africa/Lagos')
SUB = {'endpoint': 'https://push.example.com/abc', 'keys': {'p256dh': 'key123', 'auth': 'auth123'}}


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')
        self.client.cookies['tz'] = 'Africa/Lagos'


class ParserTests(TestCase):
    now = datetime(2026, 10, 18, 10, 0, tzinfo=LAGOS)  # a Sunday morning

    def check(self, text, title, when=None, priority=None, repeat=None):
        r = parse(text, self.now)
        self.assertEqual(r.title, title)
        self.assertEqual(r.due.strftime('%a %H:%M') if r.due else None, when)
        self.assertEqual(r.priority, priority)
        self.assertEqual(r.repeat, repeat)

    def test_phrases(self):
        self.check('Call mum tomorrow 7pm', 'Call mum', 'Mon 19:00')
        self.check('Pay rent every month !!', 'Pay rent', 'Mon 09:00', 'high', 'monthly')
        self.check('Submit assignment friday 11:59pm !!!', 'Submit assignment', 'Fri 23:59', 'urgent')
        self.check('Gym every monday 6am', 'Gym', 'Mon 06:00', repeat='weekly')
        self.check('Take medicine in 30 min', 'Take medicine', 'Sun 10:30')
        self.check('Meet Tunde at 7 with Ada', 'Meet Tunde with Ada', 'Sun 19:00')
        self.check('Call dad tonight', 'Call dad', 'Sun 20:00')
        self.check('Buy bread', 'Buy bread')

    def test_time_already_passed_today_moves_to_tomorrow(self):
        self.check('Standup 9am', 'Standup', 'Mon 09:00')

    def test_never_loses_the_whole_title(self):
        self.assertEqual(parse('tomorrow', self.now).title, 'tomorrow')


class QuickAddTests(Base):
    def test_quick_add_sets_date_priority_and_alarm(self):
        self.client.post(reverse('list'), {'title': 'Call mum tomorrow 7pm !!'})
        task = Task.objects.get(title='Call mum')
        self.assertEqual(task.priority, 'high')
        self.assertTrue(task.alarm_enabled)
        self.assertEqual(timezone.localtime(task.due_date, LAGOS).hour, 19)
        self.assertEqual(task.alarm_time, task.due_date)

    def test_quick_add_respects_remind_me_earlier_setting(self):
        self.user.profile.alarm_minutes_before = 15
        self.user.profile.save()
        self.client.post(reverse('list'), {'title': 'Lecture tomorrow 10am'})
        task = Task.objects.get(title='Lecture')
        self.assertEqual(task.due_date - task.alarm_time, timedelta(minutes=15))

    def test_quick_add_repeat(self):
        self.client.post(reverse('list'), {'title': 'Drink water every day'})
        task = Task.objects.get(title='Drink water')
        self.assertTrue(task.is_recurring)
        self.assertEqual(task.recurring_frequency, 'daily')

    def test_empty_quick_add_does_nothing(self):
        self.client.post(reverse('list'), {'title': '   '})
        self.assertFalse(Task.objects.exists())


class FormFixTests(Base):
    def test_editing_a_done_task_keeps_it_done(self):
        task = Task.objects.create(user=self.user, title='Old', complete=True, points_awarded=True)
        self.client.post(reverse('update', args=[task.id]), {
            'title': 'Old renamed', 'priority': 'low', 'recurring_frequency': 'none', 'recurring_interval': 1,
        })
        task.refresh_from_db()
        self.assertEqual(task.title, 'Old renamed')
        self.assertTrue(task.complete)

    def test_alarm_without_any_time_is_turned_off_instead_of_erroring(self):
        r = self.client.post(reverse('create'), {
            'title': 'No date', 'priority': 'medium', 'recurring_frequency': 'none', 'recurring_interval': 1,
            'alarm_enabled': 'on',
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Task.objects.get(title='No date').alarm_enabled)

    def test_repeat_without_date_starts_tomorrow(self):
        self.client.post(reverse('create'), {
            'title': 'Stretch', 'priority': 'low', 'is_recurring': 'on', 'recurring_frequency': 'daily',
            'recurring_interval': 1,
        })
        task = Task.objects.get(title='Stretch')
        self.assertEqual(timezone.localtime(task.due_date, LAGOS).date(), timezone.localdate(timezone=LAGOS) + timedelta(days=1))


class SafetyTests(Base):
    def test_state_changing_links_need_post(self):
        note = Note.objects.create(user=self.user, title='n', content='c')
        tpl = TaskTemplate.objects.create(user=self.user, name='t')
        TemplateItem.objects.create(template=tpl, title='x')
        for url in [reverse('archive_note', args=[note.id]), reverse('unarchive_note', args=[note.id]),
                    reverse('convert_note_to_task', args=[note.id]), reverse('use_template', args=[tpl.id])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertFalse(Task.objects.exists())

    def test_use_template_by_post(self):
        tpl = TaskTemplate.objects.create(user=self.user, name='t')
        TemplateItem.objects.create(template=tpl, title='x')
        self.client.post(reverse('use_template', args=[tpl.id]))
        self.assertTrue(Task.objects.filter(title='x').exists())


class ThemeTests(Base):
    def test_all_three_themes_save(self):
        for theme in ['blue', 'light', 'dark', 'auto']:
            r = self.client.post(reverse('update_theme'), json.dumps({'theme': theme}), content_type='application/json')
            self.assertEqual(r.status_code, 200, theme)
            self.user.profile.refresh_from_db()
            self.assertEqual(self.user.profile.theme, theme)

    def test_theme_is_painted_on_the_page(self):
        self.user.profile.theme = 'dark'
        self.user.profile.save()
        self.assertContains(self.client.get(reverse('list')), 'data-theme="dark"')

    def test_new_users_get_blue(self):
        self.assertEqual(User.objects.create_user('x', 'x@example.com', 'pw-Long-123').profile.theme, 'blue')


@override_settings(VAPID_PUBLIC_KEY='pub', VAPID_PRIVATE_KEY='priv', CRON_SECRET='s3cret')
class PushTests(Base):
    def subscribe(self):
        return self.client.post(reverse('push_subscribe'), json.dumps(SUB), content_type='application/json')

    def test_subscribe_and_unsubscribe(self):
        self.assertEqual(self.subscribe().status_code, 200)
        self.assertEqual(PushSubscription.objects.get().user, self.user)
        self.subscribe()  # same device twice = one row
        self.assertEqual(PushSubscription.objects.count(), 1)
        self.client.post(reverse('push_unsubscribe'), json.dumps({'endpoint': SUB['endpoint']}), content_type='application/json')
        self.assertFalse(PushSubscription.objects.exists())

    def test_bad_subscription_rejected(self):
        r = self.client.post(reverse('push_subscribe'), json.dumps({'endpoint': 'http://x'}), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_cron_needs_the_secret(self):
        self.assertEqual(self.client.get(reverse('cron_tick')).status_code, 404)
        self.assertEqual(self.client.get(reverse('cron_tick') + '?key=wrong').status_code, 404)

    @mock.patch('pywebpush.webpush')
    def test_cron_sends_each_ring_once_and_again_after_snooze(self, webpush):
        self.subscribe()
        task = Task.objects.create(user=self.user, title='Medicine', alarm_enabled=True,
                                   alarm_time=timezone.now() - timedelta(minutes=1))
        tick = lambda: self.client.get(reverse('cron_tick'), HTTP_X_CRON_SECRET='s3cret').json()
        self.assertEqual(tick()['alarms_sent'], 1)
        self.assertEqual(tick()['alarms_sent'], 0)  # not twice
        payload = json.loads(webpush.call_args.kwargs['data'])
        self.assertIn('Medicine', payload['title'])
        self.assertTrue(payload['actionToken'])

        task.alarm_snoozed_until = timezone.now() - timedelta(seconds=5)
        task.save()
        self.assertEqual(tick()['alarms_sent'], 1)  # snooze ended: ring again

    @mock.patch('pywebpush.webpush')
    def test_done_or_dismissed_alarms_are_not_sent(self, webpush):
        self.subscribe()
        past = timezone.now() - timedelta(minutes=1)
        Task.objects.create(user=self.user, title='a', alarm_enabled=True, alarm_time=past, complete=True)
        Task.objects.create(user=self.user, title='b', alarm_enabled=True, alarm_time=past, alarm_dismissed=True)
        self.assertEqual(notify.send_due_alarms(), 0)
        webpush.assert_not_called()

    def test_gone_devices_are_removed(self):
        from pywebpush import WebPushException
        self.subscribe()
        gone = WebPushException('gone', response=mock.Mock(status_code=410))
        with mock.patch('pywebpush.webpush', side_effect=gone):
            notify.send_push(PushSubscription.objects.get(), {'title': 't'})
        self.assertFalse(PushSubscription.objects.exists())

    def test_notification_buttons_snooze_and_dismiss(self):
        task = Task.objects.create(user=self.user, title='x', alarm_enabled=True, alarm_time=timezone.now())
        token = notify.make_action_token(task.id, self.user.id)
        self.client.logout()  # the service worker has no session/CSRF
        r = self.client.post(reverse('alarm_action'), json.dumps({'token': token, 'action': 'snooze'}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        task.refresh_from_db()
        self.assertIsNotNone(task.alarm_snoozed_until)
        self.client.post(reverse('alarm_action'), json.dumps({'token': token, 'action': 'dismiss'}), content_type='application/json')
        task.refresh_from_db()
        self.assertTrue(task.alarm_dismissed)

    def test_forged_action_token_is_refused(self):
        task = Task.objects.create(user=self.user, title='x')
        r = self.client.post(reverse('alarm_action'), json.dumps({'token': f'{task.id}:fake', 'action': 'dismiss'}), content_type='application/json')
        self.assertEqual(r.status_code, 403)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', CRON_SECRET='s3cret')
class EmailReminderTests(Base):
    def test_reminder_email_when_turned_on(self):
        self.user.profile.email_task_reminders = True
        self.user.profile.save()
        Task.objects.create(user=self.user, title='Pay rent', alarm_enabled=True, alarm_time=timezone.now() - timedelta(minutes=1),
                            due_date=timezone.now())
        notify.send_due_alarms()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Pay rent', mail.outbox[0].subject)

    def test_no_reminder_email_by_default(self):
        Task.objects.create(user=self.user, title='x', alarm_enabled=True, alarm_time=timezone.now() - timedelta(minutes=1))
        notify.send_due_alarms()
        self.assertEqual(len(mail.outbox), 0)

    def test_morning_summary_once_a_day_after_7am_local(self):
        p = self.user.profile
        p.email_daily_summary = True
        p.timezone = 'Africa/Lagos'
        p.save()
        morning = datetime(2026, 10, 19, 7, 30, tzinfo=LAGOS)
        Task.objects.create(user=self.user, title='Exam', due_date=morning.replace(hour=14))
        self.assertEqual(notify.send_daily_summaries(morning.replace(hour=6)), 0)  # too early
        self.assertEqual(notify.send_daily_summaries(morning), 1)
        self.assertEqual(notify.send_daily_summaries(morning + timedelta(minutes=5)), 0)  # once
        self.assertIn('Exam', mail.outbox[0].alternatives[0][0])

    def test_no_summary_when_nothing_is_due(self):
        p = self.user.profile
        p.email_daily_summary = True
        p.save()
        self.assertEqual(notify.send_daily_summaries(datetime(2026, 10, 19, 8, 0, tzinfo=LAGOS)), 0)


class PageTests(Base):
    def test_new_user_sees_onboarding(self):
        self.assertContains(self.client.get(reverse('list')), 'Welcome to Quantum Manager')

    def test_dashboard_counts_this_weeks_finished_tasks(self):
        Task.objects.create(user=self.user, title='d', complete=True, completed_date=timezone.now())
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.context['week_total'], 1)
        self.assertTrue(r.context['week'][-1]['is_today'])

    def test_auth_pages_load_logged_out(self):
        self.client.logout()
        for name in ['login', 'register', 'forgot_password', 'reset_link_sent', 'verification_sent', 'resend_verification', 'offline']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
