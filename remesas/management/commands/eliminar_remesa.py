from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from remesas.models import Remesa, RegistroRemesas
from django.utils import timezone


class Command(BaseCommand):
    help = 'Elimina una remesa específica de la base de datos usando su ID'

    def add_arguments(self, parser):
        parser.add_argument(
            'remesa_id',
            type=str,
            help='ID de la remesa a eliminar (ej: REM-09/18-T010-182632)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Confirma la eliminación sin pedir confirmación interactiva',
        )

    def handle(self, *args, **options):
        remesa_id = options['remesa_id']
        force = options.get('force', False)
        
        try:
            # Buscar la remesa
            with transaction.atomic():
                remesa = Remesa.objects.select_for_update().get(remesa_id=remesa_id)
                
                # Mostrar información de la remesa antes de eliminar
                self.stdout.write(
                    self.style.WARNING(f'\n=== INFORMACIÓN DE LA REMESA A ELIMINAR ===')
                )
                self.stdout.write(f'ID: {remesa.remesa_id}')
                self.stdout.write(f'Fecha: {remesa.fecha}')
                self.stdout.write(f'Estado: {remesa.get_estado_display()}')
                self.stdout.write(f'Tipo de pago: {remesa.get_tipo_pago_display() if remesa.tipo_pago else "N/A"}')
                self.stdout.write(f'Moneda: {remesa.moneda.codigo if remesa.moneda else "N/A"}')
                self.stdout.write(f'Importe: {remesa.importe}')
                self.stdout.write(f'Receptor: {remesa.receptor_nombre or "N/A"}')
                self.stdout.write(f'Gestor: {remesa.gestor.username if remesa.gestor else "N/A"}')
                
                # Mostrar valores históricos si existen
                if remesa.valor_moneda_historico:
                    self.stdout.write(f'Valor moneda histórico: {remesa.valor_moneda_historico}')
                if remesa.monto_usd_historico:
                    self.stdout.write(f'Monto USD histórico: {remesa.monto_usd_historico}')
                
                # Mostrar información de edición si existe
                if remesa.editada:
                    self.stdout.write(
                        self.style.WARNING(f'¡REMESA EDITADA!')
                    )
                    self.stdout.write(f'Fecha de edición: {remesa.fecha_edicion}')
                    if remesa.usuario_editor:
                        self.stdout.write(f'Editada por: {remesa.usuario_editor.username}')
                
                # Verificar si tiene registros asociados
                registros_count = RegistroRemesas.objects.filter(remesa=remesa).count()
                if registros_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Esta remesa tiene {registros_count} registro(s) asociado(s) que también serán eliminados.')
                    )
                    
                    # Mostrar los registros
                    registros = RegistroRemesas.objects.filter(remesa=remesa)
                    for registro in registros:
                        self.stdout.write(f'  - {registro.get_tipo_display()}: {registro.monto} ({registro.fecha_registro})')

                # Pedir confirmación si no se usa --force
                if not force:
                    self.stdout.write('\n' + '='*50)
                    confirmacion = input(
                        self.style.ERROR('¿Estás seguro de que quieres eliminar esta remesa? [y/N]: ')
                    )
                    if confirmacion.lower() not in ['y', 'yes', 'sí', 'si']:
                        self.stdout.write(
                            self.style.WARNING('Operación cancelada.')
                        )
                        return
                
                # Eliminar los registros asociados primero (CASCADE debería manejarlo, pero por claridad)
                registros_eliminados = RegistroRemesas.objects.filter(remesa=remesa).count()
                RegistroRemesas.objects.filter(remesa=remesa).delete()
                
                # Guardar información antes de eliminar para el log
                info_remesa = {
                    'id': remesa.remesa_id,
                    'importe': remesa.importe,
                    'moneda': remesa.moneda.codigo if remesa.moneda else None,
                    'estado': remesa.estado,
                    'gestor': remesa.gestor.username if remesa.gestor else None,
                    'fecha': remesa.fecha,
                    'editada': remesa.editada
                }
                
                # Eliminar la remesa
                remesa.delete()
                
                # Mensaje de éxito
                self.stdout.write('\n' + '='*50)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Remesa {remesa_id} eliminada exitosamente.')
                )
                
                if registros_eliminados > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ {registros_eliminados} registro(s) asociado(s) también eliminado(s).')
                    )
                
                # Log adicional
                self.stdout.write(f'\nDetalles de la eliminación:')
                self.stdout.write(f'- Fecha de eliminación: {timezone.now()}')
                self.stdout.write(f'- Importe eliminado: {info_remesa["importe"]} {info_remesa["moneda"] or "N/A"}')
                self.stdout.write(f'- Estado al eliminar: {info_remesa["estado"]}')
                if info_remesa['editada']:
                    self.stdout.write(f'- Era una remesa editada')

        except Remesa.DoesNotExist:
            raise CommandError(
                f'No se encontró ninguna remesa con ID: {remesa_id}\n'
                f'Verifica que el ID esté escrito correctamente.'
            )
        except Exception as e:
            raise CommandError(
                f'Error al eliminar la remesa: {str(e)}'
            )

    def handle_label(self, label, **options):
        """Override para evitar el comportamiento por defecto de los labels"""
        pass