from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from login.models import PerfilUsuario
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalcula los balances de todos los usuarios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuario',
            type=str,
            help='Recalcular balance solo para un usuario específico (username)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar detalles del cálculo',
        )

    def handle(self, *args, **options):
        usuarios = User.objects.all()
        
        if options['usuario']:
            try:
                usuarios = User.objects.filter(username=options['usuario'])
                if not usuarios.exists():
                    self.stdout.write(
                        self.style.ERROR(f'Usuario "{options["usuario"]}" no encontrado')
                    )
                    return
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error buscando usuario: {e}')
                )
                return

        total_usuarios = 0
        usuarios_actualizados = 0
        
        for usuario in usuarios:
            if not hasattr(usuario, 'perfil'):
                if options['verbose']:
                    self.stdout.write(
                        self.style.WARNING(f'Usuario {usuario.username} no tiene perfil')
                    )
                continue
                
            try:
                perfil = usuario.perfil
                balance_anterior = perfil.balance
                balance_nuevo = perfil.calcular_balance_real()
                
                # Actualizar si hay diferencia
                if balance_anterior != balance_nuevo:
                    perfil.balance = balance_nuevo
                    perfil.save()
                    usuarios_actualizados += 1
                    
                    if options['verbose']:
                        self.stdout.write(
                            f'Usuario: {usuario.username} - '
                            f'Balance anterior: {balance_anterior} USD - '
                            f'Balance nuevo: {balance_nuevo} USD'
                        )
                elif options['verbose']:
                    self.stdout.write(
                        f'Usuario: {usuario.username} - '
                        f'Balance sin cambios: {balance_nuevo} USD'
                    )
                
                total_usuarios += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error procesando usuario {usuario.username}: {e}')
                )
        
        # Resumen
        self.stdout.write(
            self.style.SUCCESS(
                f'Procesados {total_usuarios} usuarios. '
                f'{usuarios_actualizados} balances actualizados.'
            )
        )
