from __future__ import annotations

from typing import Iterable, Optional

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import NotificacionInterna


def get_admin_users_queryset():
    return User.objects.filter(
        Q(is_superuser=True) | Q(perfil__tipo_usuario='admin')
    ).distinct()


def get_domicilio_users_queryset_for_moneda(moneda) -> "User.objects":
    """Usuarios domicilio que deben recibir notificaciones para una moneda.

    Regla:
    - Si el domicilio tiene monedas asignadas, solo recibe si incluye la moneda.
    - Si NO tiene monedas asignadas, recibe para todas las monedas.
    """
    qs = User.objects.filter(is_active=True, perfil__tipo_usuario='domicilio')

    if moneda is None:
        return qs.distinct()

    # ManyToMany: incluir quienes no tienen asignaciones y quienes tienen la moneda.
    return qs.filter(
        Q(perfil__monedas_asignadas__isnull=True) | Q(perfil__monedas_asignadas=moneda)
    ).distinct()


def create_internal_notification(
    *,
    recipients: Iterable[User],
    message: str,
    actor: Optional[User] = None,
    verb: str = '',
    link: str = '',
    level: str = 'info',
    content_object: Optional[object] = None,
    content_type: Optional[ContentType] = None,
    object_id: Optional[str] = None,
) -> int:
    """Crea notificaciones internas para múltiples usuarios (deduplicadas)."""
    resolved_content_type = content_type
    resolved_object_id = object_id
    if content_object is not None:
        resolved_content_type = ContentType.objects.get_for_model(content_object, for_concrete_model=False)
        resolved_object_id = str(getattr(content_object, 'pk', '') or '')

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
            content_type=resolved_content_type,
            object_id=resolved_object_id or None,
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
    content_object: Optional[object] = None,
    content_type: Optional[ContentType] = None,
    object_id: Optional[str] = None,
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
        content_object=content_object,
        content_type=content_type,
        object_id=object_id,
    )


def notify_user_admins_and_domicilios(
    *,
    recipient: Optional[User],
    message: str,
    moneda=None,
    actor: Optional[User] = None,
    verb: str = '',
    link: str = '',
    level: str = 'info',
    content_object: Optional[object] = None,
    content_type: Optional[ContentType] = None,
    object_id: Optional[str] = None,
) -> int:
    """Notifica al usuario objetivo, admins, y domicilios por moneda."""
    recipients: list[User] = []
    if recipient is not None:
        recipients.append(recipient)
    recipients.extend(list(get_admin_users_queryset()))
    recipients.extend(list(get_domicilio_users_queryset_for_moneda(moneda)))

    return create_internal_notification(
        recipients=recipients,
        message=message,
        actor=actor,
        verb=verb,
        link=link,
        level=level,
        content_object=content_object,
        content_type=content_type,
        object_id=object_id,
    )
