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
        tz_name = request.COOKIES.get(TZ_COOKIE) or settings.DEFAULT_USER_TIMEZONE
        try:
            timezone.activate(zoneinfo.ZoneInfo(tz_name))
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            timezone.activate(zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE))
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
