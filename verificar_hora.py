import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo

# Obtener hora UTC
hora_utc = timezone.now()

# Convertir a zona horaria de Cuba
tz = ZoneInfo(settings.TIME_ZONE)
hora_local = hora_utc.astimezone(tz)

print("=" * 60)
print("VERIFICACIÓN DE ZONA HORARIA")
print("=" * 60)
print(f"Zona horaria configurada: {settings.TIME_ZONE}")
print(f"Hora UTC: {hora_utc}")
print(f"Hora local en Cuba: {hora_local}")
print(f"Fecha y hora (formato legible): {hora_local.strftime('%d/%m/%Y %I:%M:%S %p')}")
print(f"Offset UTC: {hora_local.strftime('%z')}")
print("=" * 60)
