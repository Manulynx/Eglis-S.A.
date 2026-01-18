# Modelo PagoRemesa - Documentación

## Descripción
El modelo `PagoRemesa` permite enlazar pagos específicos a remesas, facilitando el seguimiento y la gestión de pagos relacionados con una remesa particular.

## Características Principales

### 1. Relación con Remesas
- **Una remesa puede tener múltiples pagos enlazados**
- Relación `ForeignKey` que vincula cada pago con su remesa
- Acceso a los pagos desde la remesa mediante `remesa.pagos_enlazados.all()`

### 2. Atributos Idénticos a Pago
El modelo mantiene todos los atributos del modelo `Pago` original:
- `pago_id`: ID único generado automáticamente
- `tipo_pago`: Transferencia o Efectivo
- `tipo_moneda`: Moneda utilizada
- `cantidad`: Monto del pago
- `destinatario`, `telefono`, `direccion`, `carnet_identidad`: Datos del destinatario
- `tarjeta`, `comprobante_pago`: Información de transferencia
- `estado`: Pendiente, Confirmado, Cancelado
- `observaciones`: Notas adicionales

### 3. Valores Históricos Inmutables
- `valor_moneda_historico`: Valor de la moneda al momento de creación
- `monto_usd_historico`: Conversión a USD al momento de creación
- Estos valores se calculan automáticamente al crear el pago

### 4. Control de Ediciones
- `editado`: Flag que indica si el pago fue modificado
- `fecha_edicion`: Timestamp de la última edición
- `usuario_editor`: Usuario que realizó la edición

## Uso en Código

### Crear un pago enlazado a una remesa
```python
from remesas.models import PagoRemesa, Remesa, Moneda

# Obtener la remesa
remesa = Remesa.objects.get(remesa_id='REM-01/16-T100-143000')

# Crear el pago enlazado
pago = PagoRemesa.objects.create(
    remesa=remesa,
    tipo_pago='transferencia',
    tipo_moneda=Moneda.objects.get(codigo='USD'),
    cantidad=100.00,
    destinatario='Juan Pérez',
    telefono='555-1234',
    usuario=request.user
)
```

### Consultar pagos de una remesa
```python
# Obtener todos los pagos de una remesa
pagos = remesa.pagos_enlazados.all()

# Obtener solo pagos confirmados
pagos_confirmados = remesa.pagos_enlazados.filter(estado='confirmado')

# Calcular total de pagos confirmados
from django.db.models import Sum
total = remesa.pagos_enlazados.filter(estado='confirmado').aggregate(
    total=Sum('cantidad')
)['total']
```

### Confirmar un pago
```python
pago = PagoRemesa.objects.get(pago_id='PAGO-01/16-T050-143000')
if pago.puede_confirmar():
    pago.confirmar()
```

### Cancelar un pago
```python
if pago.puede_cancelar():
    pago.cancelar()
```

## Diferencias con el Modelo Pago

| Característica | Pago | PagoRemesa |
|---------------|------|------------|
| **Uso** | Pagos independientes | Pagos enlazados a remesas |
| **Relación** | Ninguna con remesas | ForeignKey a Remesa |
| **Balance** | Afecta balance del usuario | No afecta balance directamente |
| **Acceso** | `Pago.objects.all()` | `remesa.pagos_enlazados.all()` |

## Panel de Administración

El modelo está registrado en el admin de Django con:
- Vista de lista con campos principales
- Filtros por estado, tipo_pago, moneda y fecha
- Búsqueda por pago_id, destinatario y remesa_id
- Fieldsets organizados para mejor visualización
- Campos de solo lectura para valores históricos y auditoría

## Casos de Uso

1. **Gestión de Pagos Múltiples**: Una remesa grande puede dividirse en varios pagos a diferentes destinatarios
2. **Seguimiento de Pagos Parciales**: Registrar pagos parciales de una remesa hasta completar el monto total
3. **Auditoría Mejorada**: Mantener historial de todos los pagos asociados a una remesa específica
4. **Facturación Detallada**: Generar reportes detallados de pagos por remesa

## Validaciones Automáticas

- Generación automática de `pago_id` único
- Cálculo automático de valores históricos en USD
- Validación de estados para transiciones de estado
- Preservación de valores originales (inmutables)

## Migración

La tabla se creó con la migración `0033_pagoremesa.py`.
Para aplicarla:
```bash
python manage.py migrate
```

## Notas Importantes

1. **No afecta el modelo Pago existente**: Ambos modelos coexisten sin conflictos
2. **Valores históricos**: Se calculan automáticamente y no deben editarse manualmente
3. **Estado de la remesa**: Los cambios en los pagos enlazados NO cambian automáticamente el estado de la remesa
4. **Eliminación en cascada**: Si se elimina una remesa, se eliminan todos sus pagos enlazados
