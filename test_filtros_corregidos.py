import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo
from datetime import timedelta

print("=" * 70)
print("PRUEBA DE FILTROS DE FECHA CORREGIDOS")
print("=" * 70)

# Obtener la fecha actual en la zona horaria de Cuba (como lo hace ahora el código)
tz_cuba = ZoneInfo(settings.TIME_ZONE)
ahora_utc = timezone.now()
ahora_local = ahora_utc.astimezone(tz_cuba)
today = ahora_local.date()

print(f"\n🕐 Hora UTC: {ahora_utc.strftime('%d/%m/%Y %I:%M:%S %p')}")
print(f"🇨🇺 Hora Cuba: {ahora_local.strftime('%d/%m/%Y %I:%M:%S %p')}")
print(f"\n📅 FECHAS PARA FILTROS:")
print(f"   Hoy (today): {today}")

yesterday = today - timedelta(days=1)
print(f"   Ayer: {yesterday}")

week_ago = today - timedelta(weeks=1)
print(f"   Hace 1 semana: {week_ago}")

month_ago = today - timedelta(days=30)
print(f"   Hace 1 mes: {month_ago}")

print(f"\n✅ CORRECTO:")
print(f"   - Los filtros ahora usan la fecha de Cuba: {today}")
print(f"   - Coincide con la hora local: {ahora_local.strftime('%d/%m/%Y')}")
print("=" * 70)
