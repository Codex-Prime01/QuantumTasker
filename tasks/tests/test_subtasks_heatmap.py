"""Tests for task checklists (subtasks) and the dashboard streak heatmap."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tasks.models import Subtask, Task

FORM = {'priority': 'medium', 'recurring_frequency': 'none', 'recurring_interval': 1, 'alarm_tone': 'classic'}


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ada', 'ada@example.com', 'S3cure-pass-123')
        self.user.profile.email_verified = True
        self.user.profile.save()
        self.client.login(username='ada', password='S3cure-pass-123')


class SubtaskTests(Base):
    def test_create_with_checklist(self):
        items = [{'title': 'Eggs', 'done': False}, {'title': '  ', 'done': False}, {'title': 'Bread', 'done': True}]
        self.client.post(reverse('create'), {**FORM, 'title': 'Shopping', 'subtasks_json': json.dumps(items)})
        task = Task.objects.get(title='Shopping')
        self.assertEqual([(s.title, s.done) for s in task.subtasks.all()], [('Eggs', False), ('Bread', True)])

    def test_edit_updates_adds_and_removes(self):
        task = Task.objects.create(user=self.user, title='Trip')
        keep = Subtask.objects.create(task=task, title='Passport', position=0)
        Subtask.objects.create(task=task, title='Gone', position=1)
        items = [{'id': keep.id, 'title': 'Passport + visa', 'done': True}, {'title': 'Charger', 'done': False}]
        self.client.post(reverse('update', args=[task.id]), {**FORM, 'title': 'Trip', 'subtasks_json': json.dumps(items)})
        self.assertEqual([(s.title, s.done) for s in task.subtasks.all()], [('Passport + visa', True), ('Charger', False)])
        self.assertEqual(Subtask.objects.get(id=keep.id).title, 'Passport + visa')

    def test_form_without_checklist_leaves_it_alone(self):
        task = Task.objects.create(user=self.user, title='Trip')
        Subtask.objects.create(task=task, title='Passport')
        self.client.post(reverse('update', args=[task.id]), {**FORM, 'title': 'Trip renamed'})
        self.assertEqual(task.subtasks.count(), 1)

    def test_cannot_hijack_someone_elses_item_by_id(self):
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        theirs = Subtask.objects.create(task=Task.objects.create(user=other, title='Bob'), title='Bob item')
        mine = Task.objects.create(user=self.user, title='Mine')
        items = [{'id': theirs.id, 'title': 'Stolen', 'done': True}]
        self.client.post(reverse('update', args=[mine.id]), {**FORM, 'title': 'Mine', 'subtasks_json': json.dumps(items)})
        self.assertEqual(Subtask.objects.get(id=theirs.id).title, 'Bob item')
        self.assertEqual(mine.subtasks.get().title, 'Stolen')  # became a new item on my task instead

    def test_toggle_and_progress(self):
        task = Task.objects.create(user=self.user, title='Shopping')
        a = Subtask.objects.create(task=task, title='Eggs')
        Subtask.objects.create(task=task, title='Milk')
        res = self.client.post(reverse('subtask_toggle', args=[a.id]), data=json.dumps({'done': True}),
                               content_type='application/json')
        self.assertEqual(res.json(), {'success': True, 'done': True, 'progress': '1/2'})
        # Same state twice is harmless (offline replays)
        res = self.client.post(reverse('subtask_toggle', args=[a.id]), data=json.dumps({'done': True}),
                               content_type='application/json')
        self.assertTrue(res.json()['done'])

    def test_toggle_other_users_item_is_404(self):
        other = User.objects.create_user('bob', 'bob@example.com', 'S3cure-pass-123')
        theirs = Subtask.objects.create(task=Task.objects.create(user=other, title='Bob'), title='x')
        self.assertEqual(self.client.post(reverse('subtask_toggle', args=[theirs.id])).status_code, 404)

    def test_repeat_copies_checklist_unticked(self):
        task = Task.objects.create(user=self.user, title='Gym', due_date=timezone.now(),
                                   is_recurring=True, recurring_frequency='daily')
        Subtask.objects.create(task=task, title='Stretch', done=True)
        nxt = task.create_next_occurrence()
        self.assertEqual([(s.title, s.done) for s in nxt.subtasks.all()], [('Stretch', False)])

    def test_list_shows_progress(self):
        task = Task.objects.create(user=self.user, title='Shopping')
        Subtask.objects.create(task=task, title='Eggs', done=True)
        Subtask.objects.create(task=task, title='Milk')
        self.assertContains(self.client.get(reverse('list')), '1/2')


class HeatmapTests(Base):
    def test_counts_and_shape(self):
        now = timezone.now()
        for _ in range(3):
            Task.objects.create(user=self.user, title='done', complete=True, completed_date=now)
        Task.objects.create(user=self.user, title='old', complete=True, completed_date=now - timedelta(days=400))
        res = self.client.get(reverse('dashboard'))
        heat = res.context['heatmap']
        self.assertEqual(len(heat['weeks']), 20)
        self.assertTrue(all(len(w['days']) == 7 for w in heat['weeks']))
        self.assertEqual(heat['total'], 3)
        self.assertEqual(heat['active_days'], 1)
        today = [d for w in heat['weeks'] for d in w['days'] if d['today']]
        self.assertEqual(today[0]['level'], 2)  # 3 done -> level 2
        self.assertContains(res, 'Your last 20 weeks')
