import hmac
import json
import logging
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AppearanceSettingsForm,
    CustomUserForm,
    NoteForm,
    NotificationSettingsForm,
    PasswordChangeForm,
    PrivacySettingsForm,
    ProfileUpdateForm,
    TaskDefaultsForm,
    TaskForm,
    UserUpdateForm,
)
from . import nlp, notify
from .models import (
    Achievement,
    Category,
    Note,
    PushSubscription,
    Task,
    TaskTemplate,
    TemplateItem,
    UserAchievement,
    UserProfile,
    UserStats,
)
from .templatetags.qm_tags import friendly_when

logger = logging.getLogger(__name__)

# How far back an un-dismissed alarm can still ring (e.g. phone was off)
ALARM_LOOKBACK = timedelta(hours=12)
ALLOWED_TONE_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'webm'}


# ===========================================================================
# Helpers
# ===========================================================================
def _form_errors_to_messages(request, form):
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else ''
        for error in errors:
            messages.error(request, f'❌ {label + ": " if label else ""}{error}')


def _is_uploaded_tone(tone):
    return bool(tone) and (tone.startswith('/') or tone.startswith('http'))


def _save_custom_tone(request, task):
    """
    Save an uploaded ringtone with the default storage (Cloudinary in
    production, so it survives deploys) and return its URL.
    Returns None if nothing usable was uploaded.
    """
    upload = request.FILES.get('custom_tone_file')
    if not upload:
        return None

    if upload.size > settings.MAX_TONE_UPLOAD_BYTES:
        messages.warning(request, '⚠️ Sound file is too big (max 2 MB), using the classic tone.')
        return None

    ext = upload.name.rsplit('.', 1)[-1].lower() if '.' in upload.name else ''
    if ext not in ALLOWED_TONE_EXTENSIONS:
        messages.warning(request, '⚠️ Unsupported sound format, using the classic tone.')
        return None

    filename = f'alarm_tones/{request.user.id}/task_{task.id}_{uuid.uuid4().hex[:8]}.{ext}'
    saved_name = default_storage.save(filename, upload)
    return default_storage.url(saved_name)


def _send_email(subject, template_name, context, to_email):
    """Render an HTML email template and send it. Raises on failure."""
    html_message = render_to_string(template_name, context)
    msg = EmailMultiAlternatives(
        subject,
        strip_tags(html_message),
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
    )
    msg.attach_alternative(html_message, 'text/html')
    msg.send(fail_silently=False)


def send_verification_email(request, user):
    # Read fresh from the DB: user.profile can be a stale cached copy
    profile = UserProfile.objects.get(user=user)
    verification_url = settings.SITE_URL + reverse('verify_email', args=[profile.verification_token])
    _send_email(
        'Verify your email - Quantum Manager',
        'tasks/emails/verification_email.html',
        {'user': user, 'verification_url': verification_url},
        user.email,
    )


def send_password_reset_email(request, user):
    profile = UserProfile.objects.get(user=user)
    reset_url = settings.SITE_URL + reverse('reset_password', args=[profile.reset_token])
    _send_email(
        'Reset your password - Quantum Manager',
        'tasks/emails/password_reset_email.html',
        {'user': user, 'reset_url': reset_url},
        user.email,
    )


def _new_verification_token(profile):
    profile.verification_token = uuid.uuid4()
    profile.verification_token_created = timezone.now()
    profile.save(update_fields=['verification_token', 'verification_token_created'])


# ===========================================================================
# Tasks
# ===========================================================================
SORT_OPTIONS = [
    ('smart', 'What\'s next'),
    ('due_date', 'Due date'),
    ('priority', 'Priority'),
    ('created', 'Newest first'),
    ('title', 'A to Z'),
]
BUCKET_NAMES = {0: 'Overdue', 1: 'Today', 2: 'Coming up', 3: 'Anytime', 4: 'Done'}


def _today_bounds():
    """Start of today and start of tomorrow, in the user's timezone."""
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _quick_add(request):
    """
    The one-line "Add a task" box on the home screen. Understands phrases like
    "Call mum tomorrow 7pm", "Pay rent every month !!" (see nlp.py).
    """
    raw = request.POST.get('title', '').strip()
    if not raw:
        messages.error(request, 'Type something to add first.')
        return
    profile = request.user.profile
    parsed = nlp.parse(raw[:300], timezone.localtime())

    task = Task(
        user=request.user,
        title=parsed.title[:200],
        priority=parsed.priority or profile.default_priority or 'medium',
        due_date=parsed.due,
        alarm_tone=profile.default_alarm_tone if profile.default_alarm_tone not in ('', 'default') else 'classic',
    )
    if parsed.repeat:
        task.is_recurring = True
        task.recurring_frequency = parsed.repeat
    if task.due_date and profile.alarm_enabled:
        task.alarm_enabled = True
        task.alarm_time = task.due_date - timedelta(minutes=profile.alarm_minutes_before or 0)
    task.save()
    if profile.default_category_id:
        task.categories.add(profile.default_category_id)

    bits = [f'Added "{task.title}"']
    if task.due_date:
        bits.append(friendly_when(task.due_date))
    if task.is_recurring:
        bits.append(task.get_recurring_frequency_display().lower())
    message = ' · '.join(bits)
    if task.alarm_enabled:
        message += '. I\'ll remind you.'
    messages.success(request, message)


@login_required
def index(request):
    if request.method == 'POST':
        _quick_add(request)
        return redirect(request.get_full_path())

    all_tasks = Task.objects.filter(user=request.user)
    tasks = all_tasks
    profile = request.user.profile
    start_today, start_tomorrow = _today_bounds()
    now = timezone.now()

    categories = Category.objects.annotate(
        task_count=Count('task', filter=Q(task__user=request.user))
    ).order_by('name')

    search_query = request.GET.get('search', '').strip()
    if search_query:
        tasks = tasks.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))

    selected_category = None
    category_id = request.GET.get('category')
    if category_id and category_id.isdigit():
        selected_category = Category.objects.filter(id=category_id).first()
        if selected_category:
            tasks = tasks.filter(categories=selected_category)

    sort_by = request.GET.get('sort', 'smart')
    if sort_by not in dict(SORT_OPTIONS):
        sort_by = 'smart'
    order = request.GET.get('order', 'desc')
    priority_order = Case(
        When(priority='urgent', then=1),
        When(priority='high', then=2),
        When(priority='medium', then=3),
        When(priority='low', then=4),
        output_field=IntegerField(),
    )
    # Which group a task belongs in on the "What's next" view
    tasks = tasks.annotate(bucket=Case(
        When(complete=True, then=4),
        When(due_date__lt=now, then=0),
        When(due_date__lt=start_tomorrow, then=1),
        When(due_date__isnull=False, then=2),
        default=3,
        output_field=IntegerField(),
    ))
    if sort_by == 'smart':
        tasks = tasks.order_by('bucket', 'due_date', priority_order, '-completed_date', '-created')
    elif sort_by == 'due_date':
        tasks = tasks.order_by('due_date', 'created') if order == 'asc' else tasks.order_by('-due_date', '-created')
    elif sort_by == 'priority':
        tasks = tasks.order_by(priority_order, 'created')
    elif sort_by == 'title':
        tasks = tasks.order_by('title') if order == 'asc' else tasks.order_by('-title')
    else:
        tasks = tasks.order_by('created') if order == 'asc' else tasks.order_by('-created')

    from django.core.paginator import Paginator
    paginator = Paginator(tasks.prefetch_related('categories'), max(5, profile.tasks_per_page or 20))
    page = paginator.get_page(request.GET.get('page'))

    # Today's numbers for the header
    due_today = all_tasks.filter(due_date__gte=start_today, due_date__lt=start_tomorrow)
    done_today_ids = set(all_tasks.filter(
        complete=True, completed_date__gte=start_today
    ).values_list('id', flat=True))
    today_ids = set(due_today.values_list('id', flat=True)) | done_today_ids
    today_done = all_tasks.filter(id__in=today_ids, complete=True).count()
    stats = getattr(request.user, 'stats', None)

    # Keep filters when moving between pages / sorts
    keep = request.GET.copy()
    keep.pop('page', None)

    context = {
        'page': page,
        'tasks': page.object_list,
        'grouped': sort_by == 'smart',
        'bucket_names': BUCKET_NAMES,
        'categories': categories,
        'selected_category': selected_category,
        'totalTasks': all_tasks.count(),
        'pending_count': all_tasks.filter(complete=False).count(),
        'due_today_count': due_today.filter(complete=False).count(),
        'overdue_count': all_tasks.filter(complete=False, due_date__lt=now).count(),
        'today_total': len(today_ids),
        'today_done': today_done,
        'streak': stats.current_streak if stats else 0,
        'sort_by': sort_by,
        'sort_options': SORT_OPTIONS,
        'order': order,
        'search_query': search_query,
        'querystring': keep.urlencode(),
        'is_new_user': not all_tasks.exists(),
        'today_ids': today_ids,
        'filtered': bool(search_query or selected_category),
    }
    return render(request, 'tasks/index.html', context)


@login_required
def create_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                task = form.save(commit=False)
                task.user = request.user
                profile = request.user.profile
                # Alarm on but no time picked: use the user's "remind me X before" default
                if task.alarm_enabled and task.due_date and not request.POST.get('alarm_time'):
                    task.alarm_time = task.due_date - timedelta(minutes=profile.alarm_minutes_before or 0)
                task.save()  # need an id before naming the ringtone file
                form.save_m2m()

                if task.alarm_tone == 'custom':
                    tone_url = _save_custom_tone(request, task)
                    task.alarm_tone = tone_url or 'classic'
                    task.save(update_fields=['alarm_tone'])

            messages.success(request, f'✅ Task "{task.title}" created successfully!')
            recurring_info = task.get_recurring_info()
            if recurring_info:
                messages.info(request, recurring_info)
            return redirect('list')
        _form_errors_to_messages(request, form)
    else:
        profile = request.user.profile
        form = TaskForm(initial={
            'priority': profile.default_priority,
            'categories': [profile.default_category] if profile.default_category else [],
            'alarm_tone': profile.default_alarm_tone if profile.default_alarm_tone != 'default' else 'classic',
            'alarm_enabled': profile.alarm_enabled,
            'title': request.GET.get('title', '')[:200],
        })

    return render(request, 'tasks/create.html', {'form': form})


@login_required
def updateTask(request, pk):
    task = get_object_or_404(Task, id=pk, user=request.user)

    old_tone = task.alarm_tone

    if request.method == 'POST':
        old_alarm = (task.alarm_enabled, task.alarm_time)
        form = TaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            # A changed alarm should ring again, even if the old one was dismissed
            if (task.alarm_enabled, task.alarm_time) != old_alarm:
                task.alarm_dismissed = False
                task.alarm_snoozed_until = None
            if task.alarm_tone == 'custom':
                tone_url = _save_custom_tone(request, task)
                # No new file? keep the tone they uploaded before
                task.alarm_tone = tone_url or (old_tone if _is_uploaded_tone(old_tone) else 'classic')
            task.save()
            form.save_m2m()
            messages.success(request, f'✅ Task "{task.title}" updated successfully!')
            return redirect('list')
        _form_errors_to_messages(request, form)
    else:
        form = TaskForm(instance=task)

    return render(request, 'tasks/update.html', {
        'form': form,
        'task': task,
        'has_custom_tone': _is_uploaded_tone(old_tone),
    })


@login_required
def deleteTask(request, pk):
    item = get_object_or_404(Task, id=pk, user=request.user)
    if request.method == 'POST':
        title = item.title
        item.delete()
        messages.success(request, f'🗑️ Task "{title}" deleted successfully!')
        return redirect('list')
    return render(request, 'tasks/delete.html', {'item': item})


@login_required
@require_POST
def quick_toggle_complete(request, pk):
    """Tick / untick a task (AJAX). Points are only ever awarded once per task."""
    with transaction.atomic():
        task = get_object_or_404(Task.objects.select_for_update(), id=pk, user=request.user)
        task.complete = not task.complete
        response_data = {'success': True, 'complete': task.complete}
        new_achievements = []

        if task.complete:
            task.completed_date = timezone.now()
            if not task.points_awarded:
                stats, _ = UserStats.objects.get_or_create(user=request.user)
                stats.update_streak()  # also resets the daily counter on a new day
                stats.total_tasks_completed += 1
                stats.tasks_completed_today += 1
                stats.save()
                new_achievements = stats.check_achievements()
                task.points_awarded = True
        else:
            task.completed_date = None

        task.save()

        if task.complete:
            next_task = task.create_next_occurrence()
            if next_task:
                local_due = timezone.localtime(next_task.due_date)
                response_data['message'] = f'✅ Done! Next one is set for {local_due.strftime("%B %d, %Y")}'

    if new_achievements:
        response_data['new_achievements'] = [
            {'name': a.name, 'icon': a.icon, 'points': a.points, 'description': a.description}
            for a in new_achievements
        ]
        names = ', '.join(f'{a.icon} {a.name}' for a in new_achievements)
        points = sum(a.points for a in new_achievements)
        achievement_msg = f'🎉 Achievement Unlocked: {names}! (+{points} points)'
        response_data['message'] = (
            f"{response_data['message']}\n{achievement_msg}" if 'message' in response_data else achievement_msg
        )

    return JsonResponse(response_data)


# ===========================================================================
# Auth
# ===========================================================================
def registerUser(request):
    if request.user.is_authenticated:
        return redirect('list')

    if request.method == 'POST':
        form = CustomUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)

            if not settings.REQUIRE_EMAIL_VERIFICATION:
                profile.email_verified = True
                profile.save(update_fields=['email_verified'])
                login(request, user)
                messages.success(request, f'🎉 Welcome to Quantum Manager, {user.username}!')
                return redirect('list')

            _new_verification_token(profile)
            try:
                send_verification_email(request, user)
            except Exception:
                logger.exception('Verification email failed for user %s', user.pk)
                messages.warning(
                    request,
                    '⚠️ Your account was created, but we could not send the verification email. '
                    'Use "Resend verification" below to try again.',
                )
            request.session['pending_verification_email'] = user.email
            return redirect('verification_sent')
    else:
        form = CustomUserForm()

    return render(request, 'tasks/register.html', {'form': form})


def loginUser(request):
    if request.user.is_authenticated:
        return redirect('list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if settings.REQUIRE_EMAIL_VERIFICATION and not profile.email_verified:
                request.session['pending_verification_email'] = user.email
                messages.warning(request, '📧 Please verify your email first. Check your inbox (and spam).')
                return redirect('verification_sent')
            login(request, user)
            messages.success(request, f'✅ Welcome back, {user.username}!')
            next_url = request.GET.get('next', '')
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('list')
    else:
        form = AuthenticationForm()

    return render(request, 'tasks/login.html', {'form': form})


def logoutUser(request):
    logout(request)
    return redirect('login')


def verification_sent(request):
    return render(request, 'tasks/verification_sent.html', {
        'pending_email': request.session.get('pending_verification_email', ''),
    })


def verify_email(request, token):
    profile = UserProfile.objects.filter(verification_token=token).select_related('user').first()
    if not profile:
        messages.error(request, '❌ That verification link is not valid.')
        return redirect('login')
    if profile.email_verified:
        messages.info(request, 'Your email is already verified. Please log in.')
        return redirect('login')
    if not profile.is_verification_token_valid():
        request.session['pending_verification_email'] = profile.user.email
        messages.error(request, '⏰ That link has expired. We can send you a new one.')
        return redirect('resend_verification')

    profile.email_verified = True
    profile.verification_token = uuid.uuid4()  # one-time use
    profile.save(update_fields=['email_verified', 'verification_token'])
    login(request, profile.user)
    messages.success(request, f'✅ Email verified! Welcome, {profile.user.username}!')
    return redirect('list')


def resend_verification(request):
    """Works without logging in, since unverified users can't log in."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email__iexact=email).select_related('profile').first()
        if user and not user.profile.email_verified:
            _new_verification_token(user.profile)
            try:
                send_verification_email(request, user)
            except Exception:
                logger.exception('Resend verification failed for user %s', user.pk)
        # Same message either way, so nobody can test which emails have accounts
        messages.success(request, '📧 If that email needs verifying, a new link is on its way.')
        request.session['pending_verification_email'] = email
        return redirect('verification_sent')

    return render(request, 'tasks/resend_verification.html', {
        'pending_email': request.session.get('pending_verification_email', ''),
    })


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            messages.error(request, '❌ Please enter your email address.')
            return redirect('forgot_password')

        user = User.objects.filter(email__iexact=email).select_related('profile').first()
        if user:
            profile = user.profile
            profile.reset_token = uuid.uuid4()
            profile.reset_token_created = timezone.now()
            profile.save(update_fields=['reset_token', 'reset_token_created'])
            try:
                send_password_reset_email(request, user)
            except Exception:
                logger.exception('Password reset email failed for user %s', user.pk)

        # Same message whether or not the account exists
        messages.success(request, '📧 If an account uses that email, a reset link is on its way.')
        return redirect('reset_link_sent')

    return render(request, 'tasks/forgot_password.html')


def reset_link_sent(request):
    return render(request, 'tasks/reset_link_sent.html')


def reset_password(request, token):
    profile = UserProfile.objects.filter(reset_token=token).select_related('user').first()
    if not profile or not profile.is_reset_token_valid():
        messages.error(request, '⏰ That reset link is invalid or has expired. Please request a new one.')
        return redirect('forgot_password')

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if not password1 or password1 != password2:
            messages.error(request, '❌ The two passwords must match.')
            return redirect('reset_password', token=token)
        try:
            validate_password(password1, user=profile.user)
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, f'❌ {error}')
            return redirect('reset_password', token=token)

        user = profile.user
        user.set_password(password1)
        user.save()
        # Burn the token so the link can't be reused
        profile.reset_token = uuid.uuid4()
        profile.reset_token_created = None
        # Getting a reset email proves they own the address
        profile.email_verified = True
        profile.save(update_fields=['reset_token', 'reset_token_created', 'email_verified'])
        messages.success(request, '✅ Password reset! Please log in with your new password.')
        return redirect('login')

    return render(request, 'tasks/reset_password.html', {'token': token, 'username': profile.user.username})


# ===========================================================================
# Dashboard / profile / settings
# ===========================================================================
@login_required
def dashboard(request):
    user_tasks = Task.objects.filter(user=request.user)
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    total_tasks = user_tasks.count()
    completed_tasks = user_tasks.filter(complete=True).count()
    completion_rate = round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0

    priority_counts = dict(user_tasks.values_list('priority').annotate(c=Count('id')))
    priority_stats = {p: priority_counts.get(p, 0) for p in ('urgent', 'high', 'medium', 'low')}

    category_stats = [
        {'name': c.name, 'count': c.task_count, 'color': c.color}
        for c in Category.objects.annotate(
            task_count=Count('task', filter=Q(task__user=request.user))
        ).filter(task_count__gt=0).order_by('-task_count')
    ]
    top_category = max([c['count'] for c in category_stats], default=0)
    for c in category_stats:
        c['pct'] = round(c['count'] / top_category * 100) if top_category else 0

    # Tasks finished on each of the last 7 days (in the user's timezone)
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    done_dates = user_tasks.filter(
        completed_date__gte=now - timedelta(days=8)
    ).values_list('completed_date', flat=True)
    per_day = {d: 0 for d in days}
    for dt in done_dates:
        local_day = timezone.localtime(dt).date()
        if local_day in per_day:
            per_day[local_day] += 1
    peak = max(per_day.values()) or 1
    week = [
        {
            'label': 'Today' if d == today else d.strftime('%a'),
            'count': per_day[d],
            'height': max(3, round(per_day[d] / peak * 100)) if per_day[d] else 3,
            'is_today': d == today,
        }
        for d in days
    ]
    priority_total = sum(priority_stats.values())
    priority_rows = [
        {'key': key, 'label': label, 'count': priority_stats[key],
         'pct': round(priority_stats[key] / priority_total * 100) if priority_total else 0}
        for key, label in (('urgent', 'Urgent'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'))
    ]
    stats, _ = UserStats.objects.get_or_create(user=request.user)

    context = {
        'week': week,
        'week_total': sum(per_day.values()),
        'priority_rows': priority_rows,
        'stats': stats,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': total_tasks - completed_tasks,
        'completion_rate': completion_rate,
        'priority_stats': priority_stats,
        'category_stats': category_stats,
        'overdue_count': user_tasks.filter(due_date__lt=now, complete=False).count(),
        'upcoming_tasks': user_tasks.filter(
            due_date__gte=now, due_date__lte=now + timedelta(days=7), complete=False
        ).order_by('due_date')[:5],
        'recent_completed': user_tasks.filter(complete=True).order_by('-completed_date', '-created')[:5],
        'tasks_this_week': user_tasks.filter(created__gte=week_ago).count(),
        'completed_this_week': user_tasks.filter(complete=True, completed_date__gte=week_ago).count(),
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    # Build every form up front so any branch can re-render the page safely
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileUpdateForm(instance=profile_obj)
    password_form = PasswordChangeForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'profile_info':
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile_obj)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, '✅ Profile updated successfully!')
                return redirect('profile')
            messages.error(request, '❌ Please correct the errors below.')

        elif form_type == 'password_change':
            password_form = PasswordChangeForm(request.POST)
            if password_form.is_valid():
                if not request.user.check_password(password_form.cleaned_data['current_password']):
                    messages.error(request, '❌ Current password is incorrect.')
                else:
                    new_password = password_form.cleaned_data['new_password1']
                    try:
                        validate_password(new_password, user=request.user)
                    except ValidationError as exc:
                        for error in exc.messages:
                            messages.error(request, f'❌ {error}')
                    else:
                        request.user.set_password(new_password)
                        request.user.save()
                        update_session_auth_hash(request, request.user)
                        messages.success(request, '✅ Password changed successfully!')
                        return redirect('profile')
            else:
                messages.error(request, '❌ Please correct the errors below.')

    user_tasks = Task.objects.filter(user=request.user)
    total_tasks = user_tasks.count()
    completed_tasks = user_tasks.filter(complete=True).count()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': total_tasks - completed_tasks,
        'completion_rate': round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0,
        'priority_stats': user_tasks.values('priority').annotate(count=Count('id')),
    }
    return render(request, 'tasks/profile.html', context)


@login_required
def userp_settings(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    form_classes = {
        'notifications': (NotificationSettingsForm, '✅ Notification settings updated!'),
        'appearance': (AppearanceSettingsForm, '✅ Appearance settings updated!'),
        'task_defaults': (TaskDefaultsForm, '✅ Task defaults updated!'),
        'privacy': (PrivacySettingsForm, '✅ Privacy settings updated!'),
    }
    forms_by_type = {key: cls(instance=profile_obj) for key, (cls, _msg) in form_classes.items()}
    active_tab = request.GET.get('tab', 'notifications')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type in form_classes:
            form_cls, success_msg = form_classes[form_type]
            form = form_cls(request.POST, instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, success_msg)
                return redirect(f"{reverse('userp_settings')}?tab={form_type}")
            forms_by_type[form_type] = form  # re-show with errors
            active_tab = form_type
            messages.error(request, '❌ Please correct the errors below.')

        elif form_type == 'delete_account':
            if request.POST.get('confirm_delete') == request.user.username:
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, '✅ Your account has been deleted. Goodbye! 👋')
                return redirect('login')
            messages.error(request, '❌ Username confirmation did not match!')

    context = {
        'notification_form': forms_by_type['notifications'],
        'appearance_form': forms_by_type['appearance'],
        'task_defaults_form': forms_by_type['task_defaults'],
        'privacy_form': forms_by_type['privacy'],
        'active_tab': active_tab,
    }
    return render(request, 'tasks/settings.html', context)


@login_required
@require_POST
def update_theme(request):
    try:
        theme = json.loads(request.body).get('theme')
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    if theme not in dict(UserProfile.THEME_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid theme'}, status=400)
    UserProfile.objects.filter(user=request.user).update(theme=theme)
    return JsonResponse({'success': True, 'theme': theme})


# ===========================================================================
# Templates
# ===========================================================================
def _visible_template(request, pk):
    """A template the user may view/use: a default one or their own."""
    return get_object_or_404(
        TaskTemplate.objects.filter(Q(is_default=True) | Q(user=request.user)),
        id=pk,
    )


@login_required
def templates_list(request):
    return render(request, 'tasks/templates_list.html', {
        'default_templates': TaskTemplate.objects.filter(is_default=True),
        'user_templates': TaskTemplate.objects.filter(user=request.user, is_default=False),
    })


@login_required
def template_detail(request, pk):
    template = _visible_template(request, pk)
    return render(request, 'tasks/template_detail.html', {
        'template': template,
        'items': template.items.all(),
    })


@login_required
@require_POST
def use_template(request, pk):
    template = _visible_template(request, pk)
    created_tasks = template.instantiate(request.user)
    messages.success(request, f'✅ Created {len(created_tasks)} tasks from "{template.name}"!')
    return redirect('list')


@login_required
def create_template(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, '❌ Template name is required.')
            return redirect('create_template')
        template = TaskTemplate.objects.create(
            user=request.user,
            name=name[:200],
            description=request.POST.get('description', ''),
            icon=request.POST.get('icon', '📋')[:10] or '📋',
            is_default=False,
        )
        messages.success(request, f'✅ Template "{template.name}" created! Now add tasks to it.')
        return redirect('edit_template', pk=template.id)
    return render(request, 'tasks/create_template.html')


@login_required
def edit_template(request, pk):
    template = get_object_or_404(TaskTemplate, id=pk, user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_info':
            template.name = request.POST.get('name', template.name)[:200] or template.name
            template.description = request.POST.get('description', template.description)
            template.icon = request.POST.get('icon', template.icon)[:10] or template.icon
            template.save()
            messages.success(request, '✅ Template updated!')
        elif action == 'add_item':
            title = request.POST.get('title', '').strip()
            priority = request.POST.get('priority', 'medium')
            if priority not in dict(Task.PRIORITY_CHOICES):
                priority = 'medium'
            if title:
                TemplateItem.objects.create(
                    template=template,
                    title=title[:200],
                    description=request.POST.get('description', ''),
                    priority=priority,
                    order=template.items.count() + 1,
                )
                messages.success(request, f'✅ Added "{title}" to template!')
            else:
                messages.error(request, '❌ Task title is required.')
        return redirect('edit_template', pk=pk)

    return render(request, 'tasks/edit_template.html', {'template': template, 'items': template.items.all()})


@login_required
@require_POST
def delete_template_item(request, template_id, item_id):
    template = get_object_or_404(TaskTemplate, id=template_id, user=request.user)
    item = get_object_or_404(TemplateItem, id=item_id, template=template)
    title = item.title
    item.delete()
    messages.success(request, f'✅ Removed "{title}" from template.')
    return redirect('edit_template', pk=template_id)


@login_required
def delete_template(request, pk):
    template = get_object_or_404(TaskTemplate, id=pk, user=request.user)
    if request.method == 'POST':
        name = template.name
        template.delete()
        messages.success(request, f'✅ Template "{name}" deleted.')
        return redirect('templates_list')
    return render(request, 'tasks/delete_template.html', {'template': template})


@login_required
def create_template_from_tasks(request):
    if request.method == 'POST':
        task_ids = [tid for tid in request.POST.getlist('task_ids') if tid.isdigit()]
        template_name = request.POST.get('template_name', '').strip()
        if not task_ids or not template_name:
            messages.error(request, '❌ Please select tasks and provide a template name.')
            return redirect('create_template_from_tasks')

        tasks = Task.objects.filter(id__in=task_ids, user=request.user).prefetch_related('categories')
        with transaction.atomic():
            template = TaskTemplate.objects.create(
                user=request.user,
                name=template_name[:200],
                icon=request.POST.get('template_icon', '📋')[:10] or '📋',
                is_default=False,
            )
            for order, task in enumerate(tasks, 1):
                item = TemplateItem.objects.create(
                    template=template,
                    title=task.title,
                    description=task.description,
                    priority=task.priority,
                    is_recurring=task.is_recurring,
                    recurring_frequency=task.recurring_frequency,
                    order=order,
                )
                item.categories.set(task.categories.all())

        messages.success(request, f'✅ Created template "{template.name}" from {len(tasks)} tasks!')
        return redirect('templates_list')

    tasks = Task.objects.filter(user=request.user, complete=False)
    return render(request, 'tasks/create_template_from_tasks.html', {'tasks': tasks})


# ===========================================================================
# Achievements
# ===========================================================================
@login_required
def achievements_view(request):
    stats, _ = UserStats.objects.get_or_create(user=request.user)
    unlocked = {
        ua.achievement_id: ua.unlocked_at
        for ua in UserAchievement.objects.filter(user=request.user)
    }

    progress_source = {
        'tasks_completed': stats.total_tasks_completed,
        'streak': stats.current_streak,
        'consistency': stats.longest_streak,
    }

    achievements_by_type = {}
    all_achievements = Achievement.objects.all()
    for achievement in all_achievements:
        is_unlocked = achievement.id in unlocked
        if achievement.is_hidden and not is_unlocked:
            continue
        if is_unlocked:
            progress = 100
        else:
            current = progress_source.get(achievement.achievement_type, 0)
            progress = min(100, int(current / achievement.requirement * 100)) if achievement.requirement else 0

        achievements_by_type.setdefault(achievement.get_achievement_type_display(), []).append({
            'achievement': achievement,
            'is_unlocked': is_unlocked,
            'progress': progress,
            'unlocked_at': unlocked.get(achievement.id),
        })

    return render(request, 'tasks/achievements.html', {
        'stats': stats,
        'achievements_by_type': achievements_by_type,
        'total_achievements': all_achievements.count(),
        'unlocked_count': len(unlocked),
        'total_points': stats.total_points,
    })


def offline_page(request):
    return render(request, 'tasks/offline.html')


# ===========================================================================
# Notes
# ===========================================================================
@login_required
def notes_list(request):
    notes = Note.objects.filter(user=request.user, is_archived=False)
    category = request.GET.get('category')
    if category:
        notes = notes.filter(category=category)
    search_query = request.GET.get('search', '').strip()
    if search_query:
        notes = notes.filter(
            Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(tags__icontains=search_query)
        )
    return render(request, 'tasks/notes_list.html', {
        'notes': notes,
        'total_notes': Note.objects.filter(user=request.user, is_archived=False).count(),
        'pinned_count': notes.filter(is_pinned=True).count(),
        'search_query': search_query,
        'selected_category': category,
    })


@login_required
def create_note(request):
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, f'✅ Note "{note.title}" created!')
            return redirect('notes_list')
        _form_errors_to_messages(request, form)
    else:
        form = NoteForm()
    return render(request, 'tasks/create_note.html', {'form': form})


@login_required
def update_note(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Note "{note.title}" updated!')
            return redirect('notes_list')
        _form_errors_to_messages(request, form)
    else:
        form = NoteForm(instance=note)
    return render(request, 'tasks/update_note.html', {'form': form, 'note': note})


@login_required
def delete_note(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    if request.method == 'POST':
        title = note.title
        note.delete()
        messages.success(request, f'🗑️ Note "{title}" deleted!')
        return redirect('notes_list')
    return render(request, 'tasks/delete_note.html', {'note': note})


@login_required
@require_POST
def toggle_pin_note(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    note.is_pinned = not note.is_pinned
    note.save(update_fields=['is_pinned'])
    return JsonResponse({'success': True, 'is_pinned': note.is_pinned})


@login_required
@require_POST
def archive_note(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    note.is_archived = True
    note.save(update_fields=['is_archived'])
    messages.success(request, f'📦 Note "{note.title}" archived!')
    return redirect('notes_list')


@login_required
@require_POST
def unarchive_note(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    note.is_archived = False
    note.save(update_fields=['is_archived'])
    messages.success(request, f'📂 Note "{note.title}" restored!')
    return redirect('archived_notes')


@login_required
def archived_notes(request):
    notes = Note.objects.filter(user=request.user, is_archived=True)
    search_query = request.GET.get('search', '').strip()
    if search_query:
        notes = notes.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))
    return render(request, 'tasks/archived_notes.html', {
        'notes': notes,
        'total_notes': notes.count(),
        'search_query': search_query,
    })


@login_required
@require_POST
def convert_note_to_task(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    Task.objects.create(user=request.user, title=note.title, description=note.content, priority='medium')
    note.is_archived = True
    note.save(update_fields=['is_archived'])
    messages.success(request, f'✅ Note "{note.title}" converted to task!')
    return redirect('list')


def _safe_filename(name):
    cleaned = re.sub(r'[^A-Za-z0-9 _-]+', '', name).strip().replace(' ', '_')
    return (cleaned or 'note')[:60]


def _format_note(note, number=None):
    created = timezone.localtime(note.created).strftime('%B %d, %Y at %I:%M %p')
    heading = f'NOTE #{number}: {note.title}' if number else note.title
    return (
        f"{'=' * 40}\n{heading}\n{'=' * 40}\n"
        f"Category: {note.get_category_display()}\n"
        f"Created: {created}\n"
        f"Tags: {note.tags or 'None'}\n\n"
        f"{note.content}\n\n"
    )


@login_required
def export_note_as_text(request, pk):
    note = get_object_or_404(Note, id=pk, user=request.user)
    content = _format_note(note) + 'Exported from Quantum Manager\n'
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{_safe_filename(note.title)}.txt"'
    return response


@login_required
def export_all_notes(request):
    notes = Note.objects.filter(user=request.user, is_archived=False)
    now = timezone.localtime()
    parts = [
        f"MY NOTES - QUANTUM MANAGER\nTotal notes: {notes.count()}\n"
        f"Exported: {now.strftime('%B %d, %Y at %I:%M %p')}\n\n"
    ]
    parts += [_format_note(note, i) for i, note in enumerate(notes, 1)]
    parts.append('END OF EXPORT\n')
    response = HttpResponse(''.join(parts), content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="all_notes_{now.strftime("%Y%m%d")}.txt"'
    return response


# ===========================================================================
# Alarms
# ===========================================================================
def _due_alarm_tasks(user, now=None):
    """
    Tasks whose alarm should be ringing right now.

    An alarm rings when its ring time (snooze time if snoozed, otherwise the
    alarm time) has passed, it hasn't been dismissed, and it's not too old.
    No more 5-minute window: if the phone was off, it still rings when the
    app opens again.
    """
    now = now or timezone.now()
    oldest = now - ALARM_LOOKBACK
    return Task.objects.filter(user=user, complete=False, alarm_enabled=True, alarm_dismissed=False).filter(
        Q(alarm_snoozed_until__isnull=True, alarm_time__lte=now, alarm_time__gte=oldest)
        | Q(alarm_snoozed_until__isnull=False, alarm_snoozed_until__lte=now, alarm_snoozed_until__gte=oldest)
    )


@login_required
@require_GET
def check_due_tasks(request):
    tasks_data = [
        {
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'alarm_time': task.alarm_time.isoformat() if task.alarm_time else None,
            # changes after every snooze, so the page knows it's a new ring
            'ring_at': task.ring_at.isoformat() if task.ring_at else None,
            'alarm_tone': task.alarm_tone or 'classic',
        }
        for task in _due_alarm_tasks(request.user)
    ]
    response = JsonResponse({'success': True, 'due_tasks': tasks_data, 'count': len(tasks_data)})
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@require_POST
def snooze_alarm(request, pk):
    try:
        minutes = int(json.loads(request.body or '{}').get('minutes', 10))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
    minutes = max(1, min(minutes, 24 * 60))

    task = get_object_or_404(Task, id=pk, user=request.user)
    task.alarm_snoozed_until = timezone.now() + timedelta(minutes=minutes)
    task.save(update_fields=['alarm_snoozed_until'])
    return JsonResponse({
        'success': True,
        'message': f'Alarm snoozed for {minutes} minutes',
        'snoozed_until': task.alarm_snoozed_until.isoformat(),
    })


@login_required
@require_POST
def dismiss_alarm(request, pk):
    task = get_object_or_404(Task, id=pk, user=request.user)
    task.alarm_dismissed = True
    task.alarm_snoozed_until = None
    task.save(update_fields=['alarm_dismissed', 'alarm_snoozed_until'])
    return JsonResponse({'success': True})


# ===========================================================================
# Push alarms: ring even when the app is closed
# ===========================================================================
def _json_body(request):
    try:
        data = json.loads(request.body or '{}')
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


@login_required
@require_POST
def push_subscribe(request):
    """Save this browser's push address so alarms can reach it later."""
    data = _json_body(request)
    endpoint = str(data.get('endpoint', ''))[:1000]
    keys = data.get('keys') or {}
    p256dh, auth = str(keys.get('p256dh', ''))[:200], str(keys.get('auth', ''))[:100]
    if not endpoint.startswith('https://') or not p256dh or not auth:
        return JsonResponse({'success': False, 'error': 'Invalid subscription'}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:300],
        },
    )
    return JsonResponse({'success': True})


@login_required
@require_POST
def push_unsubscribe(request):
    endpoint = str(_json_body(request).get('endpoint', ''))
    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def push_test(request):
    """Send a test alarm to every device this user turned alarms on for."""
    if not notify.push_enabled():
        return JsonResponse({'success': False, 'error': 'Push is not set up on the server yet'}, status=503)
    payload = {
        'title': 'Test alarm',
        'body': 'Alarms reach this device, even with the app closed.',
        'url': reverse('list'),
        'tag': 'qm-test',
    }
    sent = sum(1 for sub in PushSubscription.objects.filter(user=request.user) if notify.send_push(sub, payload))
    return JsonResponse({'success': sent > 0, 'sent': sent})


@csrf_exempt
@require_POST
def alarm_action(request):
    """
    Snooze / dismiss buttons on a push notification. The service worker
    can't send a CSRF token, so the request carries a signed, expiring
    token that names the task and its owner instead.
    """
    data = _json_body(request)
    try:
        info = notify.read_action_token(str(data.get('token', '')))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid or expired'}, status=403)
    task = Task.objects.filter(pk=info.get('t'), user_id=info.get('u')).first()
    if not task:
        return JsonResponse({'success': False}, status=404)
    action = data.get('action')
    if action == 'snooze':
        task.alarm_snoozed_until = timezone.now() + timedelta(minutes=10)
        task.save(update_fields=['alarm_snoozed_until'])
    elif action == 'dismiss':
        task.alarm_dismissed = True
        task.alarm_snoozed_until = None
        task.save(update_fields=['alarm_dismissed', 'alarm_snoozed_until'])
    else:
        return JsonResponse({'success': False}, status=400)
    return JsonResponse({'success': True})


@csrf_exempt
def cron_tick(request):
    """
    Called every minute by a free scheduler (cron-job.org). Sends due alarms
    as push notifications / emails and the morning summaries. Protected by
    CRON_SECRET, passed as ?key=... or an X-Cron-Secret header.
    """
    secret = settings.CRON_SECRET
    given = request.headers.get('X-Cron-Secret') or request.GET.get('key', '')
    if not secret or not hmac.compare_digest(given, secret):
        return JsonResponse({'success': False}, status=404)
    result = notify.run_tick()
    return JsonResponse({'success': True, **result})
