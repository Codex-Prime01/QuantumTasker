"""Tests for the iPhone-style Alarms page, its on/off switch, and the new task sheet."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Task


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')
        self.soon = timezone.now() + timedelta(hours=3)

    def toggle(self, task, enabled):
        return self.client.post(
            reverse('toggle_alarm', args=[task.id]),
            data=json.dumps({'enabled': enabled}),
            content_type='application/json',
        )


class AlarmsPageTests(Base):
    def test_lists_upcoming_tasks_in_time_order(self):
        later = Task.objects.create(user=self.user, title='Later one', due_date=self.soon + timedelta(days=2))
        first = Task.objects.create(user=self.user, title='First one', alarm_enabled=True,
                                    due_date=self.soon, alarm_time=self.soon)
        res = self.client.get(reverse('alarms'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([t.id for t in res.context['alarms']], [first.id, later.id])
        self.assertEqual(res.context['on_count'], 1)
        self.assertContains(res, 'data-alarm-toggle')

    def test_hides_done_old_and_other_users_tasks(self):
        Task.objects.create(user=self.user, title='Done', complete=True, due_date=self.soon)
        Task.objects.create(user=self.user, title='Last week', due_date=timezone.now() - timedelta(days=7))
        Task.objects.create(user=self.user, title='No time')
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        Task.objects.create(user=other, title='Not mine', due_date=self.soon)
        res = self.client.get(reverse('alarms'))
        self.assertEqual(list(res.context['alarms']), [])
        self.assertContains(res, 'No alarms yet')

    def test_needs_login(self):
        self.client.logout()
        res = self.client.get(reverse('alarms'))
        self.assertEqual(res.status_code, 302)


class ToggleAlarmTests(Base):
    def test_turn_on_uses_due_date_and_clears_old_dismiss(self):
        task = Task.objects.create(user=self.user, title='Call mum', due_date=self.soon, alarm_dismissed=True)
        res = self.toggle(task, True)
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.alarm_enabled)
        self.assertEqual(task.alarm_time, self.soon)
        self.assertFalse(task.alarm_dismissed)

    def test_turn_on_respects_remind_me_before_setting(self):
        self.user.profile.alarm_minutes_before = 15
        self.user.profile.save()
        task = Task.objects.create(user=self.user, title='Call mum', due_date=self.soon)
        self.toggle(task, True)
        task.refresh_from_db()
        self.assertEqual(task.alarm_time, self.soon - timedelta(minutes=15))

    def test_turn_off(self):
        task = Task.objects.create(user=self.user, title='Call mum', due_date=self.soon,
                                   alarm_enabled=True, alarm_time=self.soon)
        res = self.toggle(task, False)
        self.assertEqual(res.json(), {'success': True, 'enabled': False})
        task.refresh_from_db()
        self.assertFalse(task.alarm_enabled)
        self.assertEqual(task.alarm_time, self.soon)  # the time is kept for next time

    def test_cannot_turn_on_a_time_that_passed(self):
        past = timezone.now() - timedelta(minutes=5)
        task = Task.objects.create(user=self.user, title='Too late', due_date=past, alarm_time=past)
        res = self.toggle(task, True)
        self.assertEqual(res.status_code, 400)
        self.assertIn('passed', res.json()['error'])
        task.refresh_from_db()
        self.assertFalse(task.alarm_enabled)

    def test_cannot_turn_on_without_a_time(self):
        task = Task.objects.create(user=self.user, title='Someday')
        res = self.toggle(task, True)
        self.assertEqual(res.status_code, 400)

    def test_bad_body_and_other_users_task(self):
        task = Task.objects.create(user=self.user, title='Mine', due_date=self.soon)
        res = self.client.post(reverse('toggle_alarm', args=[task.id]), data='{"enabled": "yes"}',
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        theirs = Task.objects.create(user=other, title='Theirs', due_date=self.soon)
        self.assertEqual(self.toggle(theirs, True).status_code, 404)

    def test_get_not_allowed(self):
        task = Task.objects.create(user=self.user, title='Mine', due_date=self.soon)
        self.assertEqual(self.client.get(reverse('toggle_alarm', args=[task.id])).status_code, 405)


class TaskSheetTests(Base):
    def test_create_page_has_wheel_and_fallback_date_box(self):
        res = self.client.get(reverse('create'))
        self.assertContains(res, 'id="timeWheel"')
        self.assertContains(res, 'name="due_date"')  # plain box still there if the wheel fails
        self.assertContains(res, 'switch ios-green')
        self.assertContains(res, '>Never</option>')

    def test_create_with_repeat_and_alarm_still_works(self):
        due = (timezone.localtime() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        res = self.client.post(reverse('create'), {
            'title': 'Gym',
            'priority': 'medium',
            'due_date': due.strftime('%Y-%m-%dT%H:%M'),
            'recurring_frequency': 'weekly',
            'recurring_interval': 1,
            'is_recurring': 'on',
            'alarm_enabled': 'on',
            'alarm_time': (due - timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M'),
            'alarm_tone': 'classic',
        })
        self.assertEqual(res.status_code, 302)
        task = Task.objects.get(title='Gym')
        self.assertTrue(task.is_recurring)
        self.assertEqual(task.recurring_frequency, 'weekly')
        self.assertTrue(task.alarm_enabled)
        self.assertEqual(task.due_date - task.alarm_time, timedelta(minutes=15))

    def test_edit_page_shows_delete_row(self):
        task = Task.objects.create(user=self.user, title='Edit me', due_date=self.soon)
        res = self.client.get(reverse('update', args=[task.id]))
        self.assertContains(res, 'Delete Task')
        self.assertContains(res, 'Edit Task')
