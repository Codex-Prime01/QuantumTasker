import zoneinfo

from django.conf import settings
from django.utils import timezone

TZ_COOKIE = 'tz'


class UserTimezoneMiddleware:
    """
    Show and read times in the user's own timezone.

    The browser saves its IANA timezone (e.g. "Africa/Lagos") in a cookie
    (see base.html). Dates are still stored in UTC in the database, Django
    just converts them on the way in (forms) and out (templates).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_tz = request.COOKIES.get(TZ_COOKIE, '')
        tz_name = cookie_tz or settings.DEFAULT_USER_TIMEZONE
        try:
            timezone.activate(zoneinfo.ZoneInfo(tz_name))
            valid = bool(cookie_tz)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            timezone.activate(zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE))
            valid = False

        # Remember the timezone on the profile so emails sent in the
        # background (daily summary) go out at the user's morning
        user = getattr(request, 'user', None)
        if valid and user is not None and user.is_authenticated:
            profile = getattr(user, 'profile', None)
            if profile is not None and profile.timezone != cookie_tz:
                type(profile).objects.filter(pk=profile.pk).update(timezone=cookie_tz[:64])
                profile.timezone = cookie_tz[:64]
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
