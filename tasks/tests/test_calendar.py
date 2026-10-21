"""Tests for calendar files: one task with its alarm, and the private subscribe feed."""
from datetime import datetime, timedelta, timezone as dt_tz

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks import ical
from tasks.models import Task, UserProfile

DUE = datetime(2030, 3, 4, 9, 0, tzinfo=dt_tz.utc)


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')


class IcalFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')

    def test_event_has_time_alarm_and_repeat(self):
        task = Task.objects.create(user=self.user, title='Pay rent, now; really', due_date=DUE,
                                   alarm_enabled=True, alarm_time=DUE - timedelta(minutes=15),
                                   is_recurring=True, recurring_frequency='biweekly')
        body = ical.build_calendar([task], 'https://q.example')
        self.assertIn('DTSTART:20300304T090000Z', body)
        self.assertIn('SUMMARY:Pay rent\\, now\\; really', body)
        self.assertIn('TRIGGER:-PT15M', body)
        self.assertIn('RRULE:FREQ=WEEKLY;INTERVAL=2', body)
        self.assertIn(f'UID:task-{task.id}@quantum-manager', body)
        self.assertTrue(body.startswith('BEGIN:VCALENDAR\r\n'))

    def test_no_alarm_no_valarm_and_custom_repeat(self):
        task = Task.objects.create(user=self.user, title='Water plants', due_date=DUE,
                                   is_recurring=True, recurring_frequency='custom', recurring_interval=3)
        body = ical.build_calendar([task], 'https://q.example')
        self.assertNotIn('VALARM', body)
        self.assertIn('RRULE:FREQ=DAILY;INTERVAL=3', body)

    def test_long_lines_are_folded_to_75_bytes(self):
        task = Task.objects.create(user=self.user, title='é' * 120, due_date=DUE)
        body = ical.build_calendar([task], 'https://q.example')
        for line in body.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75, line)
        # Unfolding gives the title back unchanged
        unfolded = body.replace('\r\n ', '')
        self.assertIn('SUMMARY:' + 'é' * 120, unfolded)

    def test_tasks_without_a_date_are_skipped(self):
        task = Task.objects.create(user=self.user, title='Someday')
        self.assertNotIn('BEGIN:VEVENT', ical.build_calendar([task], 'https://q.example'))


class TaskIcsTests(Base):
    def test_download(self):
        task = Task.objects.create(user=self.user, title='Dentist visit', due_date=DUE)
        res = self.client.get(reverse('task_ics', args=[task.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res['Content-Type'].startswith('text/calendar'))
        self.assertIn('dentist-visit.ics', res['Content-Disposition'])

    def test_no_date_goes_back_to_edit(self):
        task = Task.objects.create(user=self.user, title='Someday')
        res = self.client.get(reverse('task_ics', args=[task.id]))
        self.assertRedirects(res, reverse('update', args=[task.id]))

    def test_other_users_task_is_hidden(self):
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        task = Task.objects.create(user=other, title='Secret', due_date=DUE)
        self.assertEqual(self.client.get(reverse('task_ics', args=[task.id])).status_code, 404)


class FeedTests(Base):
    def test_settings_makes_a_private_link_and_feed_works_without_login(self):
        page = self.client.get(reverse('userp_settings') + '?tab=calendar')
        token = UserProfile.objects.get(user=self.user).calendar_token
        self.assertTrue(token and len(token) >= 30)
        self.assertContains(page, 'webcal://')
        soon = timezone.now() + timedelta(days=1)
        Task.objects.create(user=self.user, title='Upcoming', due_date=soon)
        Task.objects.create(user=self.user, title='Finished', due_date=soon, complete=True)
        Task.objects.create(user=self.user, title='Long ago', due_date=timezone.now() - timedelta(days=90))
        self.client.logout()
        res = self.client.get(reverse('calendar_feed', args=[token]))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('SUMMARY:Upcoming', body)
        self.assertNotIn('Finished', body)
        self.assertNotIn('Long ago', body)

    def test_link_is_not_made_until_the_tab_is_opened(self):
        self.client.get(reverse('userp_settings'))
        self.assertIsNone(UserProfile.objects.get(user=self.user).calendar_token)

    def test_reset_kills_the_old_link(self):
        old = self.user.profile.get_calendar_token()
        self.client.post(reverse('userp_settings'), {'form_type': 'calendar_reset'})
        new = UserProfile.objects.get(user=self.user).calendar_token
        self.assertNotEqual(old, new)
        self.assertEqual(self.client.get(reverse('calendar_feed', args=[old])).status_code, 404)
        self.assertEqual(self.client.get(reverse('calendar_feed', args=[new])).status_code, 200)

    def test_wrong_token_is_404(self):
        self.assertEqual(self.client.get(reverse('calendar_feed', args=['nope'])).status_code, 404)
