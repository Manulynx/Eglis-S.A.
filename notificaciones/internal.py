from __future__ import annotations

from typing import Iterable, Optional

from django.contrib.auth.models import User
from django.db.models import Q

from .models import NotificacionInterna


def get_admin_users_queryset():
    return User.objects.filter(
        Q(is_superuser=True) | Q(perfil__tipo_usuario='admin')
    ).distinct()


def create_internal_notification(
    *,
    recipients: Iterable[User],
    message: str,
    actor: Optional[User] = None,
    verb: str = '',
    link: str = '',
    level: str = 'info',
) -> int:
    """Crea notificaciones internas para múltiples usuarios (deduplicadas)."""
    unique_recipients = {}
    for user in recipients:
        if user and user.pk:
            unique_recipients[user.pk] = user

    objs = [
        NotificacionInterna(
            recipient=user,
            actor=actor,
            verb=verb,
            message=message,
            link=link,
            level=level,
        )
        for user in unique_recipients.values()
    ]

    created = NotificacionInterna.objects.bulk_create(objs)
    return len(created)


def notify_user_and_admins(
    *,
    recipient: Optional[User],
    message: str,
    actor: Optional[User] = None,
    verb: str = '',
    link: str = '',
    level: str = 'info',
) -> int:
    recipients: list[User] = []
    if recipient is not None:
        recipients.append(recipient)
    recipients.extend(list(get_admin_users_queryset()))

    return create_internal_notification(
        recipients=recipients,
        message=message,
        actor=actor,
        verb=verb,
        link=link,
        level=level,
    )
