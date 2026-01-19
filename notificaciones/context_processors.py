from __future__ import annotations

from django.utils import timezone

from .models import NotificacionInterna


def internal_notifications(request):
    """Context processor para campanita de notificaciones internas."""
    if not request.user.is_authenticated:
        return {
            'internal_unread_count': 0,
        }

    unread_count = NotificacionInterna.objects.filter(
        recipient=request.user,
        read_at__isnull=True,
    ).count()

    return {
        'internal_unread_count': unread_count,
        'internal_unread_checked_at': timezone.now(),
    }
