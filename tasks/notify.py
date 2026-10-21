"""
Reminders that reach people even when the app is closed.

`run_tick()` is called every minute by an outside scheduler (cron-job.org)
hitting /api/cron/tick/. Each run:

1. Finds alarms whose ring time has passed and that haven't been sent yet.
2. Sends a push notification to every device the owner turned alarms on for,
   plus an email if they asked for reminder emails.
3. Sends the morning summary email to people who turned it on.

Each ring is sent once: `Task.last_reminded_ring` remembers the ring time we
already sent, so a snooze (which changes the ring time) sends again.
"""
import json
import logging
import zoneinfo
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from .models import PushSubscription, Task, UserProfile

logger = logging.getLogger(__name__)

# Don't send reminders for alarms that are older than this (e.g. after downtime)
SEND_WINDOW = timedelta(hours=6)
SUMMARY_HOUR = 7  # local time
ACTION_SALT = 'qm-push-action'
ACTION_MAX_AGE = 60 * 60 * 24 * 2  # notification buttons work for 2 days


def push_enabled():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def make_action_token(task_id, user_id):
    return signing.dumps({'t': task_id, 'u': user_id}, salt=ACTION_SALT)


def read_action_token(token):
    return signing.loads(token, salt=ACTION_SALT, max_age=ACTION_MAX_AGE)


def send_push(subscription, payload):
    """Send one push. Removes subscriptions the browser has thrown away."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.as_webpush_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': f'mailto:{settings.VAPID_CLAIM_EMAIL}'},
            ttl=60 * 60,
            timeout=10,
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status in (404, 410):
            subscription.delete()  # the device unsubscribed or the app was removed
        else:
            logger.warning('Push failed for subscription %s: %s', subscription.pk, exc)
        return False
    except Exception:
        logger.exception('Push failed for subscription %s', subscription.pk)
        return False
    subscription.last_used = timezone.now()
    subscription.save(update_fields=['last_used'])
    return True


def alarm_payload(task):
    priority_word = task.get_priority_display()
    body = task.description.strip()[:120] if task.description else f'{priority_word} priority'
    return {
        'title': f'⏰ {task.title}',
        'body': body,
        'url': reverse('update', args=[task.id]),
        'tag': f'task-{task.id}',
        'actionToken': make_action_token(task.id, task.user_id),
        'requireInteraction': True,
        # No "Got it" button on the notification: it has to be stopped in the app
        'wakeCheck': task.wake_check,
    }


def _site_url(path):
    return settings.SITE_URL + path


def send_reminder_email(task):
    profile = getattr(task.user, 'profile', None)
    html = render_to_string('tasks/emails/reminder_email.html', {
        'task': task,
        'tz': _local_now(profile, timezone.now()).tzinfo if profile else zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE),
        'task_url': _site_url(reverse('update', args=[task.id])),
        'home_url': _site_url('/'),
        'settings_url': _site_url(reverse('userp_settings') + '?tab=notifications'),
    })
    msg = EmailMultiAlternatives(
        f'Reminder: {task.title}', strip_tags(html), settings.DEFAULT_FROM_EMAIL, [task.user.email]
    )
    msg.attach_alternative(html, 'text/html')
    msg.send(fail_silently=False)


def due_alarms(now):
    """Alarms that should be sent right now and haven't been sent yet."""
    oldest = now - SEND_WINDOW
    tasks = Task.objects.filter(
        complete=False, alarm_enabled=True, alarm_dismissed=False, user__isnull=False
    ).filter(
        Q(alarm_snoozed_until__isnull=True, alarm_time__lte=now, alarm_time__gte=oldest)
        | Q(alarm_snoozed_until__isnull=False, alarm_snoozed_until__lte=now, alarm_snoozed_until__gte=oldest)
    ).select_related('user', 'user__profile')
    return [t for t in tasks if t.last_reminded_ring != t.ring_at]


def send_due_alarms(now=None):
    now = now or timezone.now()
    sent = 0
    for task in due_alarms(now):
        ring = task.ring_at
        # Mark first, so a slow send can't make the next tick send it twice
        updated = Task.objects.filter(pk=task.pk).exclude(last_reminded_ring=ring).update(last_reminded_ring=ring)
        if not updated:
            continue

        if push_enabled():
            payload = alarm_payload(task)
            for sub in PushSubscription.objects.filter(user=task.user):
                if send_push(sub, payload):
                    sent += 1

        profile = getattr(task.user, 'profile', None)
        if profile and profile.email_notifications and profile.email_task_reminders and task.user.email:
            try:
                send_reminder_email(task)
                sent += 1
            except Exception:
                logger.exception('Reminder email failed for task %s', task.pk)
    return sent


def _local_now(profile, now):
    try:
        tz = zoneinfo.ZoneInfo(profile.timezone or settings.DEFAULT_USER_TIMEZONE)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        tz = zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE)
    return now.astimezone(tz)


def send_daily_summaries(now=None):
    now = now or timezone.now()
    sent = 0
    profiles = UserProfile.objects.filter(
        email_notifications=True, email_daily_summary=True
    ).select_related('user')
    for profile in profiles:
        local = _local_now(profile, now)
        if local.hour < SUMMARY_HOUR or profile.last_summary_date == local.date():
            continue
        # Claim today first so two ticks can't both send
        claimed = UserProfile.objects.filter(pk=profile.pk).exclude(
            last_summary_date=local.date()
        ).update(last_summary_date=local.date())
        if not claimed:
            continue

        start_of_day = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        pending = Task.objects.filter(user=profile.user, complete=False)
        overdue = list(pending.filter(due_date__lt=start_of_day).order_by('due_date')[:10])
        today = list(pending.filter(due_date__gte=start_of_day, due_date__lt=end_of_day).order_by('due_date'))
        if not overdue and not today:
            continue  # nothing to say, don't send an empty email

        html = render_to_string('tasks/emails/daily_summary_email.html', {
            'user': profile.user,
            'overdue': overdue,
            'today': today,
            'tz': local.tzinfo,
            'home_url': _site_url('/'),
            'settings_url': _site_url(reverse('userp_settings') + '?tab=notifications'),
        })
        msg = EmailMultiAlternatives(
            f'Your day: {len(today)} due today' + (f', {len(overdue)} overdue' if overdue else ''),
            strip_tags(html), settings.DEFAULT_FROM_EMAIL, [profile.user.email],
        )
        msg.attach_alternative(html, 'text/html')
        try:
            msg.send(fail_silently=False)
            sent += 1
        except Exception:
            logger.exception('Daily summary failed for user %s', profile.user_id)
    return sent


def run_tick(now=None):
    now = now or timezone.now()
    return {
        'alarms_sent': send_due_alarms(now),
        'summaries_sent': send_daily_summaries(now),
    }
