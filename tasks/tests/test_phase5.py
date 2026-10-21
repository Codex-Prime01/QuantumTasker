"""Tests for calendar view, wake-check alarms, bedtime mode and shared lists."""
import json
import zoneinfo
from datetime import time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks import notify
from tasks.models import ListItem, SharedList, Task, UserStats


def local(dt):
    """A stored (UTC) time shown in the user's timezone."""
    return dt.astimezone(zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE))


def make_user(name):
    user = User.objects.create_user(name, f'{name}@example.com', 'S3cure-pass-123')
    user.profile.email_verified = True
    user.profile.save()
    return user


class Base(TestCase):
    def setUp(self):
        self.user = make_user('ada')
        self.client.login(username='ada', password='S3cure-pass-123')
        # Same timezone in the test and in the app's requests (like a real phone)
        tz = settings.DEFAULT_USER_TIMEZONE
        self.client.cookies['tz'] = tz
        timezone.activate(zoneinfo.ZoneInfo(tz))
        self.addCleanup(timezone.deactivate)

    def post_json(self, url, body=None):
        return self.client.post(url, data=json.dumps(body or {}), content_type='application/json')


class CalendarViewTests(Base):
    def test_month_grid_and_selected_day(self):
        due = timezone.localtime().replace(hour=15, minute=0, second=0, microsecond=0)
        Task.objects.create(user=self.user, title='Dentist', due_date=due, priority='high')
        res = self.client.get(reverse('calendar_view'), {'day': due.date().isoformat()})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['weeks']), 6)
        self.assertContains(res, 'Dentist')
        today_cell = [d for w in res.context['weeks'] for d in w if d['today']][0]
        self.assertEqual(today_cell['dots'], ['high'])

    def test_bad_month_falls_back_to_this_month(self):
        self.assertEqual(self.client.get(reverse('calendar_view'), {'month': 'banana'}).status_code, 200)

    def test_plus_prefills_date(self):
        res = self.client.get(reverse('create'), {'due': '2030-05-06T09:00'})
        self.assertContains(res, '2030-05-06T09:00')


class WakeCheckTests(Base):
    def test_notification_cannot_dismiss_a_wake_check_alarm(self):
        task = Task.objects.create(user=self.user, title='Wake', alarm_enabled=True,
                                   alarm_time=timezone.now(), wake_check=True)
        payload = notify.alarm_payload(task)
        self.assertTrue(payload['wakeCheck'])
        res = self.post_json(reverse('alarm_action'), {'token': payload['actionToken'], 'action': 'dismiss'})
        self.assertEqual(res.status_code, 403)
        task.refresh_from_db()
        self.assertFalse(task.alarm_dismissed)
        # Snoozing from the notification is still fine
        self.assertEqual(self.post_json(reverse('alarm_action'), {'token': payload['actionToken'], 'action': 'snooze'}).status_code, 200)

    def test_saved_from_the_form(self):
        due = (timezone.localtime() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        self.client.post(reverse('create'), {'title': 'Up', 'priority': 'medium', 'recurring_frequency': 'none',
                                             'recurring_interval': 1, 'alarm_tone': 'classic', 'due_date': due,
                                             'alarm_enabled': 'on', 'wake_check': 'on'})
        self.assertTrue(Task.objects.get(title='Up').wake_check)


class BedtimeTests(Base):
    def turn_on(self, **extra):
        data = {'bedtime_enabled': 'on', 'bedtime': '22:30', 'wake_time': '06:45', 'wind_down_minutes': '30'}
        data.update(extra)
        return self.client.post(reverse('bedtime'), data)

    def test_turning_on_makes_two_daily_alarms_hidden_from_tasks(self):
        self.assertRedirects(self.turn_on(wake_check_on_wake='on'), reverse('alarms'))
        wind = Task.objects.get(user=self.user, kind='bedtime')
        wake = Task.objects.get(user=self.user, kind='wake')
        self.assertEqual(local(wake.alarm_time).time(), time(6, 45))
        self.assertEqual(local(wind.due_date).time(), time(22, 30))
        self.assertEqual(wind.due_date - wind.alarm_time, timedelta(minutes=30))
        self.assertTrue(wake.wake_check and wake.is_recurring)
        listing = self.client.get(reverse('list'))
        self.assertNotContains(listing, 'Wake up')
        self.assertContains(self.client.get(reverse('alarms')), '10:30 PM')

    def test_changing_times_replaces_alarms_and_off_removes_them(self):
        self.turn_on()
        self.turn_on(wake_time='07:15')
        self.assertEqual(Task.objects.filter(user=self.user, kind='wake').count(), 1)
        self.client.post(reverse('bedtime'), {'bedtime': '22:30', 'wake_time': '07:15', 'wind_down_minutes': '30'})
        self.assertFalse(Task.objects.filter(user=self.user, kind__in=('wake', 'bedtime')).exists())

    def test_stopping_the_wake_alarm_sets_tomorrows(self):
        self.turn_on()
        wake = Task.objects.get(user=self.user, kind='wake')
        self.post_json(reverse('dismiss_alarm', args=[wake.id]))
        wake.refresh_from_db()
        self.assertTrue(wake.complete)
        nxt = Task.objects.get(user=self.user, kind='wake', complete=False)
        self.assertEqual(nxt.due_date - wake.due_date, timedelta(days=1))
        # Alarms don't earn points or count toward the streak
        self.assertFalse(UserStats.objects.filter(user=self.user, total_tasks_completed__gt=0).exists())


class SharedListTests(Base):
    def setUp(self):
        super().setUp()
        self.bob = make_user('bob')
        self.groceries = SharedList.objects.create(owner=self.user, name='Groceries')

    def as_bob(self):
        self.client.logout()
        self.client.login(username='bob', password='S3cure-pass-123')

    def test_create_add_tick_and_state(self):
        res = self.client.post(reverse('lists'), {'name': 'Trip', 'emoji': '✈️'})
        trip = SharedList.objects.get(name='Trip')
        self.assertRedirects(res, reverse('list_detail', args=[trip.pk]))
        data = self.post_json(reverse('list_add_item', args=[trip.pk]), {'text': 'Passport'}).json()
        item_id = data['state']['items'][0]['id']
        data = self.post_json(reverse('list_toggle_item', args=[item_id]), {'done': True}).json()
        self.assertTrue(data['state']['items'][0]['done'])
        self.assertEqual(data['state']['items'][0]['by'], 'ada')

    def test_strangers_cannot_see_or_change_a_list(self):
        item = ListItem.objects.create(shared_list=self.groceries, text='Milk', added_by=self.user)
        self.as_bob()
        self.assertEqual(self.client.get(reverse('list_detail', args=[self.groceries.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('list_state', args=[self.groceries.pk])).status_code, 404)
        self.assertEqual(self.post_json(reverse('list_toggle_item', args=[item.id]), {'done': True}).status_code, 404)
        self.assertEqual(self.post_json(reverse('list_add_item', args=[self.groceries.pk]), {'text': 'x'}).status_code, 404)
        item.refresh_from_db()
        self.assertFalse(item.done)

    def test_invite_link_needs_a_tap_to_join(self):
        url = reverse('list_join', args=[self.groceries.invite_token])
        self.as_bob()
        page = self.client.get(url)
        self.assertContains(page, 'Join "Groceries"?')
        self.assertFalse(self.groceries.members.filter(id=self.bob.id).exists())  # just opening it isn't joining
        self.assertRedirects(self.client.post(url), reverse('list_detail', args=[self.groceries.pk]))
        self.assertTrue(self.groceries.members.filter(id=self.bob.id).exists())
        self.assertEqual(self.post_json(reverse('list_add_item', args=[self.groceries.pk]), {'text': 'Eggs'}).status_code, 200)

    def test_privacy_switch_blocks_joining(self):
        self.bob.profile.allow_shared_lists = False
        self.bob.profile.save()
        self.as_bob()
        url = reverse('list_join', args=[self.groceries.invite_token])
        self.assertContains(self.client.post(url), 'Shared lists are off for you')
        self.assertFalse(self.groceries.members.filter(id=self.bob.id).exists())

    def test_new_link_kills_old_one(self):
        old = self.groceries.invite_token
        self.client.post(reverse('list_manage', args=[self.groceries.pk]), {'action': 'reset_link'})
        self.groceries.refresh_from_db()
        self.assertNotEqual(old, self.groceries.invite_token)
        self.assertEqual(self.client.get(reverse('list_join', args=[old])).status_code, 404)

    def test_only_owner_can_delete_member_can_leave(self):
        self.groceries.members.add(self.bob)
        self.as_bob()
        self.client.post(reverse('list_manage', args=[self.groceries.pk]), {'action': 'delete'})
        self.assertTrue(SharedList.objects.filter(pk=self.groceries.pk).exists())
        self.client.post(reverse('list_manage', args=[self.groceries.pk]), {'action': 'leave'})
        self.assertFalse(self.groceries.members.filter(id=self.bob.id).exists())

    def test_email_shown_only_if_member_allows_it(self):
        self.groceries.members.add(self.bob)
        state = self.client.get(reverse('list_state', args=[self.groceries.pk])).json()
        bob = [m for m in state['members'] if m['id'] == self.bob.id][0]
        self.assertEqual(bob['email'], '')
        self.bob.profile.show_email = True
        self.bob.profile.save()
        state = self.client.get(reverse('list_state', args=[self.groceries.pk])).json()
        bob = [m for m in state['members'] if m['id'] == self.bob.id][0]
        self.assertEqual(bob['email'], 'bob@example.com')

    def test_offline_replay_of_an_add_happens_once(self):
        url = reverse('list_add_item', args=[self.groceries.pk])
        for _ in range(2):
            self.client.post(url, data=json.dumps({'text': 'Bread'}), content_type='application/json', HTTP_X_QM_OP='op-bread')
        self.assertEqual(self.groceries.items.filter(text='Bread').count(), 1)
