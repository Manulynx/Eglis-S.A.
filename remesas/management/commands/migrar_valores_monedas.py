from django.core.management.base import BaseCommand
from django.db import transaction
from remesas.models import TipoValorMoneda, ValorMoneda, Moneda
from login.models import PerfilUsuario


class Command(BaseCommand):
    help = 'Migra los valores actuales y comerciales de monedas al nuevo sistema de tipos de valores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula la migración sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY RUN - No se harán cambios reales'))
        
        with transaction.atomic():
            # 1. Crear tipos de valores por defecto si no existen
            tipo_actual, created = TipoValorMoneda.objects.get_or_create(
                nombre='Actual',
                defaults={
                    'descripcion': 'Valor actual de la moneda (migrado automáticamente)',
                    'orden': 1,
                    'activo': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado tipo de valor: {tipo_actual.nombre}')
                )
            else:
                self.stdout.write(f'- Tipo de valor "{tipo_actual.nombre}" ya existe')
            
            tipo_comercial, created = TipoValorMoneda.objects.get_or_create(
                nombre='Comercial',
                defaults={
                    'descripcion': 'Valor comercial de la moneda (migrado automáticamente)',
                    'orden': 2,
                    'activo': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado tipo de valor: {tipo_comercial.nombre}')
                )
            else:
                self.stdout.write(f'- Tipo de valor "{tipo_comercial.nombre}" ya existe')

            # 2. Migrar valores existentes de las monedas
            monedas_migradas = 0
            valores_creados = 0
            
            for moneda in Moneda.objects.all():
                # Migrar valor_actual
                valor_actual_obj, created = ValorMoneda.objects.get_or_create(
                    moneda=moneda,
                    tipo_valor=tipo_actual,
                    defaults={'valor': moneda.valor_actual}
                )
                
                if created:
                    valores_creados += 1
                    self.stdout.write(f'  ✓ Migrado valor actual de {moneda.codigo}: {moneda.valor_actual}')
                elif valor_actual_obj.valor != moneda.valor_actual:
                    if not dry_run:
                        valor_actual_obj.valor = moneda.valor_actual
                        valor_actual_obj.save()
                    self.stdout.write(f'  ↻ Actualizado valor actual de {moneda.codigo}: {moneda.valor_actual}')
                
                # Migrar valor_comercial
                valor_comercial_obj, created = ValorMoneda.objects.get_or_create(
                    moneda=moneda,
                    tipo_valor=tipo_comercial,
                    defaults={'valor': moneda.valor_comercial}
                )
                
                if created:
                    valores_creados += 1
                    self.stdout.write(f'  ✓ Migrado valor comercial de {moneda.codigo}: {moneda.valor_comercial}')
                elif valor_comercial_obj.valor != moneda.valor_comercial:
                    if not dry_run:
                        valor_comercial_obj.valor = moneda.valor_comercial
                        valor_comercial_obj.save()
                    self.stdout.write(f'  ↻ Actualizado valor comercial de {moneda.codigo}: {moneda.valor_comercial}')
                
                monedas_migradas += 1

            # 3. Asignar tipo de valor por defecto a usuarios que no lo tengan
            usuarios_actualizados = 0
            
            for perfil in PerfilUsuario.objects.filter(tipo_valor_moneda__isnull=True):
                if not dry_run:
                    perfil.tipo_valor_moneda = tipo_actual
                    perfil.save()
                usuarios_actualizados += 1
                self.stdout.write(f'  ✓ Asignado tipo de valor por defecto a usuario: {perfil.user.username}')

            # 4. Resumen
            self.stdout.write(self.style.SUCCESS('\n=== RESUMEN DE MIGRACIÓN ==='))
            self.stdout.write(f'Tipos de valores creados: {2 if tipo_actual and tipo_comercial else 0}')
            self.stdout.write(f'Monedas procesadas: {monedas_migradas}')
            self.stdout.write(f'Valores de monedas creados/actualizados: {valores_creados}')
            self.stdout.write(f'Usuarios actualizados: {usuarios_actualizados}')
            
            if dry_run:
                # Rollback en dry run
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('\nDRY RUN: No se guardaron cambios'))
            else:
                self.stdout.write(self.style.SUCCESS('\n✓ Migración completada exitosamente'))
