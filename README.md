# Quantum Manager (QuantumTasker)

A Django task manager built to stop people forgetting things: tasks with due
dates, alarms, repeating tasks, templates, notes and achievements. It installs
on your phone as a PWA.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set DEBUG=True and a SECRET_KEY
python manage.py migrate
python manage.py create_categories
python manage.py create_achievements
python manage.py create_default_templates
python manage.py runserver
```

Without a `BREVO_API_KEY`, emails are printed in the terminal instead of sent,
and new users skip email verification.

## Run the tests

```bash
DEBUG=True python manage.py test tasks
```

## Deploying on Render

Build command: `./build.sh` · Start command: from the `Procfile`.

Environment variables to set in the Render dashboard:

| Variable | What it's for |
| --- | --- |
| `SECRET_KEY` | Long random string. Required. |
| `DEBUG` | `False` |
| `DATABASE_URL` | Set automatically when you attach a Render Postgres DB |
| `BREVO_API_KEY` | Sends verification / reset emails over HTTPS. Render's free plan blocks SMTP ports, so plain SMTP can't work there. |
| `DEFAULT_FROM_EMAIL` | Sender address. Must be a verified sender in Brevo. |
| `CLOUDINARY_URL` | Stores avatars and custom ringtones. Render's disk is wiped on every deploy. |
| `SITE_URL` | Optional. Public URL used in email links. |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Push alarms. Make them once with `python manage.py generate_vapid_keys`. |
| `CRON_SECRET` | Any long random string. Protects the reminder job below. |

### The reminder job (alarms with the app closed, reminder emails, morning summary)

Render's free plan has no cron jobs, so use a free scheduler such as
[cron-job.org](https://cron-job.org) to open this URL **every minute**:

```
https://YOUR-SITE.onrender.com/api/cron/tick/?key=YOUR_CRON_SECRET
```

Each run sends any alarms that just came due (once per ring, again after a
snooze) and the 7 AM summary emails. Pinging every minute also stops the free
Render service from going to sleep.

## How times work

Dates are stored in UTC. The browser reports its timezone in a `tz` cookie and
the `UserTimezoneMiddleware` shows and reads times in that zone, so "3pm" means
3pm where the user is.

## How alarms work

While the app is open (tab or installed PWA), it asks `/api/check-due-tasks/`
every 30 seconds. Any alarm whose time has passed and that hasn't been
dismissed rings: sound, an on-screen popup, and a system notification (shown
through the service worker so it also works on Android). Snooze pushes the
ring time forward; Dismiss stops it for good.

With the push keys and the reminder job set up, alarms also arrive as normal
phone/computer notifications with **Snooze** and **Got it** buttons while the app
is closed. Each person turns this on per device (home screen banner, or
Settings → Reminders). On iPhone, the app must be added to the Home Screen first.

## Quick add

The box on the home screen understands plain phrases (see `tasks/nlp.py`):
`Call mum tomorrow 7pm`, `Pay rent every month !!`, `Gym every monday 6am`,
`Take medicine in 30 min`. `!!` means high priority, `!!!` urgent.
