from django.conf import settings

from .tones import TONE_GROUPS, tone_catalog


def app_context(request):
    """Values every page needs: theme, push key and the sidebar counts."""
    theme = 'blue'
    profile = None
    nav_counts = {}
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, 'profile', None)
        if profile is not None:
            theme = profile.theme or 'blue'
        # Small counts for the sidebar. Imported here to avoid app-loading issues.
        from datetime import timedelta
        from django.utils import timezone
        from .models import Note, Task
        start_tomorrow = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        open_tasks = Task.objects.filter(user=user, kind='task', complete=False)
        nav_counts = {
            'tasks': open_tasks.count(),
            'notes': Note.objects.filter(user=user, is_archived=False).count(),
            # Overdue + due today: the number on the app icon
            'due': open_tasks.filter(due_date__lt=start_tomorrow).count(),
        }
    match = getattr(request, 'resolver_match', None)
    return {
        'tone_groups': TONE_GROUPS,
        'tone_catalog': tone_catalog() if user is not None and user.is_authenticated else {},
        'qm_theme': theme,
        'qm_profile': profile,
        'push_public_key': settings.VAPID_PUBLIC_KEY,
        'nav_counts': nav_counts,
        'url_name': match.url_name if match else '',
    }
