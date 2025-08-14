#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eglis.settings')
django.setup()

from remesas.models import Remesa

# Verificar datos en la base de datos
total_remesas = Remesa.objects.count()
pendientes = Remesa.objects.filter(estado='pendiente').count()
confirmadas = Remesa.objects.filter(estado='confirmada').count()
completadas = Remesa.objects.filter(estado='completada').count()
canceladas = Remesa.objects.filter(estado='cancelada').count()

print("=== ESTADÍSTICAS DE REMESAS ===")
print(f"Total de remesas: {total_remesas}")
print(f"Pendientes: {pendientes}")
print(f"Confirmadas: {confirmadas}")
print(f"Completadas: {completadas}")
print(f"Canceladas: {canceladas}")

# Mostrar algunos ejemplos de estados si existen
if total_remesas > 0:
    print("\n=== EJEMPLOS DE REMESAS ===")
    for remesa in Remesa.objects.all()[:5]:
        print(f"ID: {remesa.remesa_id} - Estado: {remesa.estado}")

# Verificar si hay estados diferentes a los esperados
estados_unicos = Remesa.objects.values_list('estado', flat=True).distinct()
print(f"\n=== ESTADOS ÚNICOS EN LA BD ===")
for estado in estados_unicos:
    count = Remesa.objects.filter(estado=estado).count()
    print(f"{estado}: {count}")
