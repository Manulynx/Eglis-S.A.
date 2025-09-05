from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from login.models import PerfilUsuario

class Command(BaseCommand):
    help = 'Sincroniza los tipos de usuario en los perfiles con el status de superuser'

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

        usuarios_corregidos = 0
        perfiles_creados = 0
        usuarios_revisados = 0

        for user in User.objects.all():
            usuarios_revisados += 1
            
            # Verificar si tiene perfil
            if not hasattr(user, 'perfil'):
                tipo_usuario = 'admin' if user.is_superuser else 'gestor'
                
                if dry_run:
                    self.stdout.write(
                        f'CREAR PERFIL: Usuario {user.username} necesita perfil tipo {tipo_usuario}'
                    )
                else:
                    PerfilUsuario.objects.create(user=user, tipo_usuario=tipo_usuario)
                    perfiles_creados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Perfil creado para {user.username} tipo {tipo_usuario}')
                    )
                continue

            # Verificar consistencia de tipo de usuario
            perfil = user.perfil
            tipo_esperado = 'admin' if user.is_superuser else perfil.tipo_usuario
            
            # Solo cambiar si es superuser y no tiene tipo admin
            if user.is_superuser and perfil.tipo_usuario != 'admin':
                if dry_run:
                    self.stdout.write(
                        f'CORREGIR: {user.username} (superuser) tiene tipo {perfil.tipo_usuario}, debería ser admin'
                    )
                else:
                    perfil.tipo_usuario = 'admin'
                    perfil.save()
                    usuarios_corregidos += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Corregido {user.username}: {perfil.tipo_usuario} → admin')
                    )
            
            # Verificar si no-superuser tiene tipo admin (inconsistencia inversa)
            elif not user.is_superuser and perfil.tipo_usuario == 'admin':
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f'ADVERTENCIA: {user.username} (no-superuser) tiene tipo admin')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Usuario {user.username} no es superuser pero tiene tipo admin. No se cambia automáticamente.')
                    )

        # Resumen
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY-RUN completado. Revisados {usuarios_revisados} usuarios.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Sincronización completada: {usuarios_revisados} usuarios revisados, '
                    f'{perfiles_creados} perfiles creados, {usuarios_corregidos} tipos corregidos.'
                )
            )
