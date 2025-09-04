from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from remesas.models import Remesa, Pago
from login.models import PerfilUsuario
from decimal import Decimal


class Command(BaseCommand):
    help = 'Elimina todas las remesas y pagos, y resetea todos los balances de usuarios a cero'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma que quieres eliminar TODOS los datos de remesas y pagos',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'ADVERTENCIA: Este comando eliminará TODAS las remesas y pagos de la base de datos '
                    'y reseteará todos los balances de usuarios a cero.\n\n'
                    'Para confirmar, ejecuta el comando con --confirm:\n'
                    'python manage.py reset_transacciones --confirm'
                )
            )
            return

        # Confirmar una vez más
        confirmacion = input(
            'Esta acción eliminará TODOS los datos de remesas y pagos y no se puede deshacer. '
            'Escribe "CONFIRMAR" para continuar: '
        )
        
        if confirmacion != 'CONFIRMAR':
            self.stdout.write(self.style.ERROR('Operación cancelada.'))
            return

        try:
            with transaction.atomic():
                # Contar datos antes de eliminar
                total_remesas = Remesa.objects.count()
                total_pagos = Pago.objects.count()
                total_usuarios = User.objects.count()

                self.stdout.write(f'Datos encontrados:')
                self.stdout.write(f'  - Remesas: {total_remesas}')
                self.stdout.write(f'  - Pagos: {total_pagos}')
                self.stdout.write(f'  - Usuarios: {total_usuarios}')
                self.stdout.write('')

                # Eliminar todas las remesas
                if total_remesas > 0:
                    self.stdout.write('Eliminando todas las remesas...')
                    Remesa.objects.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Eliminadas {total_remesas} remesas')
                    )

                # Eliminar todos los pagos
                if total_pagos > 0:
                    self.stdout.write('Eliminando todos los pagos...')
                    Pago.objects.all().delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Eliminados {total_pagos} pagos')
                    )

                # Resetear balances de todos los usuarios
                self.stdout.write('Reseteando balances de usuarios...')
                balances_actualizados = 0
                
                for usuario in User.objects.all():
                    try:
                        # Crear perfil si no existe
                        perfil, created = PerfilUsuario.objects.get_or_create(
                            usuario=usuario,
                            defaults={
                                'balance': Decimal('0.00'),
                                'tipo_usuario': 'gestor'
                            }
                        )
                        
                        # Resetear balance a cero
                        if perfil.balance != Decimal('0.00') or created:
                            balance_anterior = perfil.balance
                            perfil.balance = Decimal('0.00')
                            perfil.save()
                            balances_actualizados += 1
                            
                            if created:
                                self.stdout.write(f'  - Usuario {usuario.username}: Perfil creado con balance $0.00')
                            else:
                                self.stdout.write(f'  - Usuario {usuario.username}: ${balance_anterior} → $0.00')
                    
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  - Error con usuario {usuario.username}: {str(e)}')
                        )

                self.stdout.write(
                    self.style.SUCCESS(f'✓ Actualizados {balances_actualizados} balances de usuarios')
                )

                # Resumen final
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('🎉 RESETEO COMPLETADO:'))
                self.stdout.write(f'  ✓ {total_remesas} remesas eliminadas')
                self.stdout.write(f'  ✓ {total_pagos} pagos eliminados')
                self.stdout.write(f'  ✓ {balances_actualizados} balances reseteados a $0.00')
                self.stdout.write('')
                self.stdout.write('La base de datos está ahora limpia y lista para nuevos datos.')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error durante el reseteo: {str(e)}')
            )
            raise
