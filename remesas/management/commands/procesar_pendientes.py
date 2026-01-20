from __future__ import annotations

import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from remesas.models import Remesa, Pago, PagoRemesa
from notificaciones.internal import create_internal_notification, get_admin_users_queryset


class Command(BaseCommand):
    help = (
        "Notifica a admins a las 23h si sigue pendiente y cancela automáticamente a las 24h "
        "(Remesa, Pago y PagoRemesa)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No guarda cambios; solo muestra lo que haría.",
        )
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Corre en loop (útil para un worker/clock).",
        )
        parser.add_argument(
            "--interval-minutes",
            type=int,
            default=10,
            help="Intervalo del loop en minutos (default: 10).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        loop: bool = options["loop"]
        interval_minutes: int = options["interval_minutes"]

        if loop:
            self.stdout.write(self.style.WARNING("Ejecutando en modo loop..."))
            while True:
                self._run_once(dry_run=dry_run)
                time.sleep(max(1, interval_minutes) * 60)
        else:
            self._run_once(dry_run=dry_run)

    def _run_once(self, *, dry_run: bool) -> None:
        now = timezone.now()
        threshold_23h = now - timedelta(hours=23)
        threshold_24h = now - timedelta(hours=24)

        total_notificados = 0
        total_cancelados = 0

        # 1) Cancelaciones (24h)
        total_cancelados += self._cancelar_remesas(threshold_24h, dry_run=dry_run)
        total_cancelados += self._cancelar_pagos(threshold_24h, dry_run=dry_run)
        total_cancelados += self._cancelar_pagos_remesa(threshold_24h, dry_run=dry_run)

        # 2) Notificaciones (23h) para los que siguen pendientes
        total_notificados += self._notificar_remesas(threshold_23h, dry_run=dry_run)
        total_notificados += self._notificar_pagos(threshold_23h, dry_run=dry_run)
        total_notificados += self._notificar_pagos_remesa(threshold_23h, dry_run=dry_run)

        self.stdout.write(
            self.style.SUCCESS(
                f"procesar_pendientes: notificados={total_notificados}, cancelados={total_cancelados}, dry_run={dry_run}"
            )
        )

    def _admins(self):
        return list(get_admin_users_queryset())

    def _cancelar_remesas(self, threshold_24h, *, dry_run: bool) -> int:
        qs = Remesa.objects.filter(estado="pendiente", fecha__lte=threshold_24h)
        count = 0
        for remesa in qs.iterator():
            if dry_run:
                self.stdout.write(f"[dry-run] Cancelaría remesa {remesa.remesa_id}")
                count += 1
                continue

            with transaction.atomic():
                # Releer con lock para evitar carreras
                remesa_locked = Remesa.objects.select_for_update().get(pk=remesa.pk)
                if remesa_locked.estado != "pendiente":
                    continue
                remesa_locked._skip_whatsapp = True
                remesa_locked.cancelado_por_tiempo = True
                remesa_locked.cancelado_por_tiempo_en = timezone.now()
                if remesa_locked.cancelar():
                    count += 1
        return count

    def _cancelar_pagos(self, threshold_24h, *, dry_run: bool) -> int:
        qs = Pago.objects.filter(estado="pendiente", fecha_creacion__lte=threshold_24h)
        count = 0
        for pago in qs.iterator():
            if dry_run:
                self.stdout.write(f"[dry-run] Cancelaría pago {pago.pago_id}")
                count += 1
                continue

            with transaction.atomic():
                pago_locked = Pago.objects.select_for_update().get(pk=pago.pk)
                if pago_locked.estado != "pendiente":
                    continue
                pago_locked._skip_whatsapp = True
                pago_locked.cancelado_por_tiempo = True
                pago_locked.cancelado_por_tiempo_en = timezone.now()
                if pago_locked.cancelar():
                    count += 1
        return count

    def _cancelar_pagos_remesa(self, threshold_24h, *, dry_run: bool) -> int:
        qs = PagoRemesa.objects.filter(estado="pendiente", fecha_creacion__lte=threshold_24h)
        count = 0
        for pago in qs.iterator():
            if dry_run:
                self.stdout.write(f"[dry-run] Cancelaría pago remesa {pago.pago_id}")
                count += 1
                continue

            with transaction.atomic():
                pago_locked = PagoRemesa.objects.select_for_update().get(pk=pago.pk)
                if pago_locked.estado != "pendiente":
                    continue
                pago_locked._skip_whatsapp = True
                pago_locked.cancelado_por_tiempo = True
                pago_locked.cancelado_por_tiempo_en = timezone.now()
                if pago_locked.cancelar():
                    count += 1
        return count

    def _notificar_remesas(self, threshold_23h, *, dry_run: bool) -> int:
        qs = Remesa.objects.filter(
            estado="pendiente",
            fecha__lte=threshold_23h,
            notificado_pendiente_23h_en__isnull=True,
        )
        admins = self._admins()
        if not admins:
            return 0

        count = 0
        for remesa in qs.iterator():
            link = reverse("remesas:detalle_remesa", args=[remesa.id])
            msg = (
                f"Remesa {remesa.remesa_id} lleva ~23h pendiente. "
                "Se cancelará automáticamente a las 24h si continúa pendiente."
            )

            if dry_run:
                self.stdout.write(f"[dry-run] Notificaría remesa 23h: {remesa.remesa_id}")
                count += 1
                continue

            with transaction.atomic():
                remesa_locked = Remesa.objects.select_for_update().get(pk=remesa.pk)
                if remesa_locked.estado != "pendiente" or remesa_locked.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=remesa_locked.gestor,
                    verb="remesa_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                remesa_locked.notificado_pendiente_23h_en = timezone.now()
                remesa_locked.save(update_fields=["notificado_pendiente_23h_en"])
                count += 1
        return count

    def _notificar_pagos(self, threshold_23h, *, dry_run: bool) -> int:
        qs = Pago.objects.filter(
            estado="pendiente",
            fecha_creacion__lte=threshold_23h,
            notificado_pendiente_23h_en__isnull=True,
        )
        admins = self._admins()
        if not admins:
            return 0

        count = 0
        for pago in qs.iterator():
            link = reverse("remesas:detalle_pago", args=[pago.id])
            msg = (
                f"Pago {pago.pago_id} lleva ~23h pendiente. "
                "Se cancelará automáticamente a las 24h si continúa pendiente."
            )

            if dry_run:
                self.stdout.write(f"[dry-run] Notificaría pago 23h: {pago.pago_id}")
                count += 1
                continue

            with transaction.atomic():
                pago_locked = Pago.objects.select_for_update().get(pk=pago.pk)
                if pago_locked.estado != "pendiente" or pago_locked.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=pago_locked.usuario,
                    verb="pago_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                pago_locked.notificado_pendiente_23h_en = timezone.now()
                pago_locked.save(update_fields=["notificado_pendiente_23h_en"])
                count += 1
        return count

    def _notificar_pagos_remesa(self, threshold_23h, *, dry_run: bool) -> int:
        qs = PagoRemesa.objects.select_related("remesa").filter(
            estado="pendiente",
            fecha_creacion__lte=threshold_23h,
            notificado_pendiente_23h_en__isnull=True,
        )
        admins = self._admins()
        if not admins:
            return 0

        count = 0
        for pago in qs.iterator():
            remesa = getattr(pago, "remesa", None)
            link = (
                reverse("remesas:detalle_remesa", args=[remesa.id])
                if remesa is not None
                else reverse("remesas:registro_transacciones")
            )
            msg = (
                f"Pago {pago.pago_id} (en remesa {remesa.remesa_id if remesa else ''}) lleva ~23h pendiente. "
                "Se cancelará automáticamente a las 24h si continúa pendiente."
            ).strip()

            if dry_run:
                self.stdout.write(f"[dry-run] Notificaría pago remesa 23h: {pago.pago_id}")
                count += 1
                continue

            with transaction.atomic():
                pago_locked = PagoRemesa.objects.select_for_update().select_related("remesa").get(pk=pago.pk)
                if pago_locked.estado != "pendiente" or pago_locked.notificado_pendiente_23h_en is not None:
                    continue

                create_internal_notification(
                    recipients=admins,
                    actor=pago_locked.usuario,
                    verb="pago_remesa_pendiente_23h",
                    message=msg,
                    link=link,
                    level="warning",
                )
                pago_locked.notificado_pendiente_23h_en = timezone.now()
                pago_locked.save(update_fields=["notificado_pendiente_23h_en"])
                count += 1
        return count
