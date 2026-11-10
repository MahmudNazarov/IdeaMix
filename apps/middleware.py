"""Request middleware for IdeaMix."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import UserActivity

logger = logging.getLogger(__name__)

# Presence is refreshed at most once per minute per session. Without the
# throttle every page view would write to the database, which is wasteful on
# SQLite and unnecessary for a seven-day chart.
ONLINE_TRACK_INTERVAL_SECONDS = 60


class OnlineTrackingMiddleware:
    """Record the daily presence of authenticated users.

    The dashboard chart only needs one row per user per day, so requests are
    aggregated into ``UserActivity`` instead of a log table.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            self._track(request)
        except Exception:  # noqa: BLE001 - telemetry must never break a page
            logger.exception('Не удалось сохранить активность пользователя')
        return self.get_response(request)

    def _track(self, request):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return

        now = timezone.now()
        session = getattr(request, 'session', None)
        interval = getattr(
            settings, 'ONLINE_TRACK_INTERVAL_SECONDS', ONLINE_TRACK_INTERVAL_SECONDS
        )

        if session is not None:
            last_tracked = session.get('online_tracked_at')
            try:
                recently_tracked = (
                    last_tracked is not None
                    and now.timestamp() - float(last_tracked) < interval
                )
            except (TypeError, ValueError):
                recently_tracked = False
            if recently_tracked:
                return

        self._store(user.pk, now)

        if session is not None:
            session['online_tracked_at'] = now.timestamp()

    @staticmethod
    def _store(user_id, now):
        today = timezone.localdate(now)
        updated = UserActivity.objects.filter(user_id=user_id, date=today).update(
            last_seen=now,
            requests=F('requests') + 1,
        )
        if updated:
            return
        UserActivity.objects.get_or_create(
            user_id=user_id,
            date=today,
            defaults={
                'first_seen': now,
                'last_seen': now,
                'requests': 1,
            },
        )
