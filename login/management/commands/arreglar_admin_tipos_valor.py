from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from login.models import PerfilUsuario
from remesas.models import TipoValorMoneda

class Command(BaseCommand):
    help = 'Arregla los perfiles de usuarios admin asegurando que tengan tipo de valor de moneda asignado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué cambios se harían sin aplicarlos',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN: Solo mostrando cambios sin aplicarlos')
            )

        admins_corregidos = 0
        perfiles_creados = 0
        admins_revisados = 0

        # Obtener tipo de valor por defecto
        tipo_valor_defecto = TipoValorMoneda.get_tipo_por_defecto()
        if not tipo_valor_defecto:
            self.stdout.write(
                self.style.ERROR('No hay tipos de valor de moneda configurados. Ejecute primero: python manage.py migrar_valores_monedas')
            )
            return

        # Revisar todos los usuarios admin
        for user in User.objects.filter(is_superuser=True):
            admins_revisados += 1
            
            # Verificar si tiene perfil
            if not hasattr(user, 'perfil'):
                if dry_run:
                    self.stdout.write(
                        f'CREAR PERFIL: Admin {user.username} necesita perfil con tipo valor {tipo_valor_defecto.nombre}'
                    )
                else:
                    PerfilUsuario.objects.create(
                        user=user, 
                        tipo_usuario='admin',
                        tipo_valor_moneda=tipo_valor_defecto
                    )
                    perfiles_creados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Perfil creado para admin {user.username} con tipo valor {tipo_valor_defecto.nombre}')
                    )
                continue

            # Verificar perfil existente
            perfil = user.perfil
            perfil_actualizado = False
            
            # Verificar tipo de usuario
            if perfil.tipo_usuario != 'admin':
                if dry_run:
                    self.stdout.write(
                        f'CORREGIR TIPO: Admin {user.username} tiene tipo {perfil.tipo_usuario}, debería ser admin'
                    )
                else:
                    perfil.tipo_usuario = 'admin'
                    perfil_actualizado = True
                    self.stdout.write(
                        self.style.SUCCESS(f'Tipo usuario corregido para {user.username}: {perfil.tipo_usuario} → admin')
                    )
            
            # Verificar tipo de valor de moneda
            if not perfil.tipo_valor_moneda:
                if dry_run:
                    self.stdout.write(
                        f'ASIGNAR TIPO VALOR: Admin {user.username} no tiene tipo de valor asignado, se asignará {tipo_valor_defecto.nombre}'
                    )
                else:
                    perfil.tipo_valor_moneda = tipo_valor_defecto
                    perfil_actualizado = True
                    self.stdout.write(
                        self.style.SUCCESS(f'Tipo valor asignado para {user.username}: {tipo_valor_defecto.nombre}')
                    )
            
            # Guardar cambios si hubo actualizaciones
            if perfil_actualizado and not dry_run:
                perfil.save()
                admins_corregidos += 1

        # Resumen
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"RESUMEN DE LA CORRECCIÓN")
        self.stdout.write(f"{'='*50}")
        self.stdout.write(f"Admins revisados: {admins_revisados}")
        self.stdout.write(f"Perfiles creados: {perfiles_creados}")
        self.stdout.write(f"Perfiles corregidos: {admins_corregidos}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nPara aplicar los cambios ejecute el comando sin --dry-run')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✅ Corrección completada exitosamente')
            )
