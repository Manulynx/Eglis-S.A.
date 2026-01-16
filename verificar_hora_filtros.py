import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from django.utils import timezone
from django.conf import settings
from zoneinfo import ZoneInfo

# Obtener hora actual
ahora_utc = timezone.now()

# Convertir a zona horaria local de Cuba
tz_cuba = ZoneInfo(settings.TIME_ZONE)
ahora_local = ahora_utc.astimezone(tz_cuba)

# Mostrar información detallada
print("=" * 70)
print("VERIFICACIÓN DE HORA ACTUAL DEL SISTEMA")
print("=" * 70)
print(f"\nZona horaria configurada: {settings.TIME_ZONE}")
print(f"USE_TZ: {settings.USE_TZ}")
print(f"\n📅 HORA UTC:")
print(f"   {ahora_utc}")
print(f"   Fecha: {ahora_utc.strftime('%d/%m/%Y')}")
print(f"   Hora: {ahora_utc.strftime('%I:%M:%S %p')}")
print(f"\n🇨🇺 HORA LOCAL EN CUBA:")
print(f"   {ahora_local}")
print(f"   Fecha: {ahora_local.strftime('%d/%m/%Y')}")
print(f"   Hora: {ahora_local.strftime('%I:%M:%S %p')}")
print(f"   Offset: {ahora_local.strftime('%z')}")
print(f"\n📊 PARA FILTROS:")
print(f"   timezone.now(): {timezone.now()}")
print(f"   timezone.now().date(): {timezone.now().date()}")
print(f"   timezone.now() convertido a Cuba: {timezone.now().astimezone(tz_cuba)}")
print(f"   Fecha en Cuba: {timezone.now().astimezone(tz_cuba).date()}")
print("=" * 70)

# Simular lo que hace el filtro de "hoy"
print("\n🔍 SIMULACIÓN DE FILTRO 'HOY':")
print("-" * 70)
today = timezone.now().date()
print(f"today = timezone.now().date() = {today}")
print(f"\nEsto filtraría registros con:")
print(f"  fecha__date = {today}")
print("\n⚠️ PROBLEMA DETECTADO:")
print("  timezone.now() devuelve hora UTC")
print("  .date() extrae solo la fecha de UTC")
print(f"  Si son las 9:30 PM en Cuba ({ahora_local.strftime('%I:%M %p')})")
print(f"  pero en UTC son las {ahora_utc.strftime('%I:%M %p')}")
print(f"  entonces la fecha puede ser diferente!")
print("=" * 70)
