from django.conf import settings


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
        from .models import Note, Task
        nav_counts = {
            'tasks': Task.objects.filter(user=user, complete=False).count(),
            'notes': Note.objects.filter(user=user, is_archived=False).count(),
        }
    match = getattr(request, 'resolver_match', None)
    return {
        'qm_theme': theme,
        'qm_profile': profile,
        'push_public_key': settings.VAPID_PUBLIC_KEY,
        'nav_counts': nav_counts,
        'url_name': match.url_name if match else '',
    }
