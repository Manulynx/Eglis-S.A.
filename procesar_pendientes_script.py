#!/usr/bin/env python3
"""Script independiente para PythonAnywhere/cron.

- Notifica a admins cuando Remesa/Pago/PagoRemesa lleva ~30h en estado pendiente.

Cómo usar (ejemplo PythonAnywhere Tasks):
  python3 /home/TU_USUARIO/tu_proyecto/procesar_pendientes_script.py

Ajusta la ruta del proyecto en sys.path.append(...) si hace falta.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import django


# ====== Configurar Django ======
# Cambia este path por el de tu proyecto en PythonAnywhere (carpeta donde vive manage.py)
# Ejemplo:
# sys.path.append('/home/TU_USUARIO/Eglis-S.A')
#
# Si lo ejecutas desde la raíz del proyecto normalmente no hace falta, pero en PythonAnywhere sí.
PROJECT_PATH = os.environ.get("DJANGO_PROJECT_PATH")
if PROJECT_PATH:
    sys.path.append(PROJECT_PATH)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "eglis.settings"))

django.setup()

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from notificaciones.internal import create_internal_notification, get_admin_users_queryset
from remesas.models import Pago, PagoRemesa, Remesa


def procesar_pendientes() -> dict:
    """Ejecuta una pasada de notificaciones."""

    ahora = timezone.now()
    limite_notificar = ahora - timedelta(hours=30)

    admins = list(get_admin_users_queryset())

    stats = {
        "remesas_notificadas": 0,
        "pagos_notificados": 0,
        "pagos_remesa_notificados": 0,
        "remesas_canceladas": 0,
        "pagos_cancelados": 0,
        "pagos_remesa_cancelados": 0,
        "admins": len(admins),
    }

    # Notificar (30h) solo una vez
    if not admins:
        return stats

    # Remesas
    for remesa in Remesa.objects.filter(
        estado="pendiente",
        fecha__lte=limite_notificar,
        notificado_pendiente_23h_en__isnull=True,
    ).iterator():
        try:
            link = reverse("remesas:detalle_remesa", args=[remesa.id])
            msg = (
                f"Remesa {remesa.remesa_id} lleva ~30h pendiente."
            )

            with transaction.atomic():
                r = Remesa.objects.select_for_update().get(pk=remesa.pk)
                if r.estado != "pendiente" or r.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=r.gestor,
                    verb="remesa_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                r.notificado_pendiente_23h_en = timezone.now()
                r.save(update_fields=["notificado_pendiente_23h_en"])
                stats["remesas_notificadas"] += 1
        except Exception as e:
            print(f"Error notificando remesa {remesa.remesa_id}: {e}")

    # Pagos
    for pago in Pago.objects.filter(
        estado="pendiente",
        fecha_creacion__lte=limite_notificar,
        notificado_pendiente_23h_en__isnull=True,
    ).iterator():
        try:
            link = reverse("remesas:detalle_pago", args=[pago.id])
            msg = (
                f"Pago {pago.pago_id} lleva ~30h pendiente."
            )

            with transaction.atomic():
                p = Pago.objects.select_for_update().get(pk=pago.pk)
                if p.estado != "pendiente" or p.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=p.usuario,
                    verb="pago_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                p.notificado_pendiente_23h_en = timezone.now()
                p.save(update_fields=["notificado_pendiente_23h_en"])
                stats["pagos_notificados"] += 1
        except Exception as e:
            print(f"Error notificando pago {pago.pago_id}: {e}")

    # Pagos remesa
    for pago in PagoRemesa.objects.select_related("remesa").filter(
        estado="pendiente",
        fecha_creacion__lte=limite_notificar,
        notificado_pendiente_23h_en__isnull=True,
    ).iterator():
        try:
            remesa = getattr(pago, "remesa", None)
            link = (
                reverse("remesas:detalle_remesa", args=[remesa.id])
                if remesa is not None
                else reverse("remesas:registro_transacciones")
            )
            msg = (
                f"Pago {pago.pago_id} (en remesa {remesa.remesa_id if remesa else ''}) lleva ~30h pendiente."
            ).strip()

            with transaction.atomic():
                pr = PagoRemesa.objects.select_for_update().select_related("remesa").get(pk=pago.pk)
                if pr.estado != "pendiente" or pr.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=pr.usuario,
                    verb="pago_remesa_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                pr.notificado_pendiente_23h_en = timezone.now()
                pr.save(update_fields=["notificado_pendiente_23h_en"])
                stats["pagos_remesa_notificados"] += 1
        except Exception as e:
            print(f"Error notificando pago remesa {pago.pago_id}: {e}")

    return stats


if __name__ == "__main__":
    print(f"[{datetime.now()}] Iniciando procesar_pendientes...")

    try:
        resultado = procesar_pendientes()
        print(f"Resultado: {resultado}")
        sys.exit(0)
    except Exception as e:
        print(f"Error en la ejecución: {e}")
        sys.exit(1)
