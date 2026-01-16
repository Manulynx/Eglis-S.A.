from django.core.management.base import BaseCommand
from django.db import transaction
from remesas.models import ValorMoneda, TipoValorMoneda, Moneda


class Command(BaseCommand):
    help = 'Limpia valores duplicados en la tabla ValorMoneda'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Encontrar duplicados
            duplicados = []
            for moneda in Moneda.objects.all():
                for tipo in TipoValorMoneda.objects.all():
                    valores = ValorMoneda.objects.filter(moneda=moneda, tipo_valor=tipo)
                    if valores.count() > 1:
                        # Mantener el más reciente, eliminar los demás
                        valor_mantener = valores.order_by('-fecha_actualizacion').first()
                        valores_eliminar = valores.exclude(id=valor_mantener.id)
                        count = valores_eliminar.count()
                        if count > 0:
                            duplicados.append(f"Moneda {moneda.codigo} - Tipo {tipo.nombre}: {count} duplicados")
                            valores_eliminar.delete()
            
            if duplicados:
                self.stdout.write(
                    self.style.SUCCESS(f'Limpieza completada. Duplicados eliminados:')
                )
                for duplicado in duplicados:
                    self.stdout.write(f"  - {duplicado}")
            else:
                self.stdout.write(
                    self.style.SUCCESS('No se encontraron duplicados.')
                )
