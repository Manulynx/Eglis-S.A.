# Rol de Domicilio y Monedas Asignadas - Documentación

## Cambios Implementados

### 1. Nuevo Rol de Usuario: Domicilio

Se agregó un nuevo tipo de usuario llamado **"Domicilio"** al sistema.

#### Características del Rol Domicilio:
- **Acceso Restringido**: Los usuarios con rol domicilio solo pueden acceder a:
  - Página principal (home)
  - Páginas de perfil personal
  - Página de cambio de contraseña
  - Página de logout
  
- **Sin Acceso a**: Remesas, pagos, reportes, configuraciones, etc.

#### Tipos de Usuario Actuales:
1. **Admin**: Acceso completo al sistema
2. **Gestor**: Puede crear remesas y ver su información
3. **Contable**: Puede ver reportes y balances
4. **Domicilio**: Solo puede ver la página principal (nuevo)

### 2. Monedas Asignadas a Usuarios

Se agregó la funcionalidad para asignar monedas específicas a gestores y domicilios.

#### Características:
- **Campo ManyToMany**: Relación de muchos a muchos entre PerfilUsuario y Moneda
- **Aplicable a**: Gestores y Domicilios
- **No aplicable a**: Administradores y Contables (tienen acceso a todas las monedas)

#### Comportamiento:
1. **Admin y Contable**: Siempre tienen acceso a **todas las monedas** sin restricciones. El campo de asignación de monedas NO es visible para estos roles.
2. **Gestor y Domicilio**:
   - **Sin monedas asignadas**: Pueden utilizar **todas las monedas activas** del sistema (comportamiento por defecto)
   - **Con monedas asignadas**: Solo pueden utilizar las monedas específicas asignadas

### 3. Métodos Agregados al Perfil

#### `puede_usar_moneda(moneda)`
Verifica si un usuario puede usar una moneda específica.

```python
# Ejemplo de uso
if request.user.perfil.puede_usar_moneda(moneda_usd):
    # Permitir la operación
    pass
```

#### `get_monedas_disponibles()`
Retorna un QuerySet con las monedas que el usuario puede utilizar.

```python
# Ejemplo de uso
monedas_disponibles = request.user.perfil.get_monedas_disponibles()
```

### 4. Middleware DomicilioAccessMiddleware

Se creó un middleware personalizado que restringe automáticamente el acceso de usuarios con rol domicilio.

#### Ubicación:
`eglis/autenticacion/middleware.py`

#### Funcionamiento:
- Intercepta todas las peticiones
- Si el usuario es tipo "domicilio", verifica la URL
- Redirige a la home si intenta acceder a páginas no permitidas

### 5. Actualización del Admin de Django

El panel de administración se actualizó para gestionar las monedas asignadas:

#### Cambios en el Admin:
- Campo `monedas_asignadas` visible en el perfil de usuario
- Widget de selección múltiple (filter_horizontal)
- Descripción explicativa del funcionamiento

#### Ubicación:
`login/admin.py`

## Migración de Base de Datos

Se creó automáticamente la migración:
- **Archivo**: `login/migrations/0006_perfilususuario_monedas_asignadas_and_more.py`
- **Cambios**:
  1. Agregar campo `monedas_asignadas` (ManyToManyField)
  2. Actualizar choices de `tipo_usuario` para incluir 'domicilio'

## Uso en el Sistema

### Para Asignar Monedas a un Usuario:

1. **Desde el Admin de Django**:
   - Ir a "Usuarios" o "Perfiles de Usuario"
   - Editar el perfil del gestor/domicilio
   - En la sección "Monedas Disponibles", seleccionar las monedas permitidas
   - Guardar

2. **Desde código Python**:
```python
# Asignar monedas a un usuario
usuario = User.objects.get(username='gestor1')
moneda_usd = Moneda.objects.get(codigo='USD')
moneda_eur = Moneda.objects.get(codigo='EUR')

usuario.perfil.monedas_asignadas.add(moneda_usd, moneda_eur)
```

### Para Verificar Monedas Disponibles en Vistas:

```python
def mi_vista(request):
    # Obtener monedas disponibles para el usuario actual
    monedas = request.user.perfil.get_monedas_disponibles()
    
    # En el formulario, filtrar por monedas disponibles
    form.fields['moneda'].queryset = monedas
    
    return render(request, 'template.html', {'monedas': monedas})
```

### Para Validar antes de Crear una Transacción:

```python
def crear_remesa(request):
    moneda_seleccionada = request.POST.get('moneda')
    moneda = Moneda.objects.get(id=moneda_seleccionada)
    
    # Verificar si el usuario puede usar esta moneda
    if not request.user.perfil.puede_usar_moneda(moneda):
        messages.error(request, 'No tiene permiso para usar esta moneda')
        return redirect('remesas:lista')
    
    # Continuar con la creación de la remesa...
```

## Próximos Pasos Recomendados

1. **Actualizar formularios de remesas y pagos** para filtrar monedas según el usuario
2. **Agregar validaciones en las vistas** para verificar permisos de moneda
3. **Crear interfaz específica para domicilios** en la página principal
4. **Agregar tests unitarios** para los nuevos métodos y middleware

## Notas Importantes

- Los **administradores** siempre tienen acceso a todas las monedas, sin importar las asignaciones
- Los **contables** también tienen acceso a todas las monedas
- Si un **gestor o domicilio** no tiene monedas asignadas, puede usar **todas** las monedas activas
- El middleware de domicilio se ejecuta después del middleware de autenticación
- Los usuarios domicilio **SÍ** pueden acceder a la página principal y ver los valores de cambio

## Archivos Modificados

1. `login/models.py` - Agregado campo `monedas_asignadas` y métodos
2. `login/admin.py` - Actualizado admin para mostrar monedas asignadas
3. `eglis/autenticacion/middleware.py` - Agregado `DomicilioAccessMiddleware`
4. `eglis/settings.py` - Agregado middleware en MIDDLEWARE
5. `login/migrations/0006_perfilusuario_monedas_asignadas_and_more.py` - Nueva migración

## Soporte

Para cualquier duda o problema con la implementación, consultar con el equipo de desarrollo.
