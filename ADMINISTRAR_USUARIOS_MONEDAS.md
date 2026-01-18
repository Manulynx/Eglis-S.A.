# Integración de Rol Domicilio y Monedas Asignadas en Administrar Usuarios

## Cambios Implementados

### 1. Actualización del Template `administrar_usuarios.html`

#### Formulario de Crear Usuario:
- ✅ Agregada opción "Domicilio" en el select de tipo de usuario
- ✅ Agregado campo de selección múltiple para monedas asignadas
- ✅ El campo de monedas se muestra/oculta automáticamente según el tipo de usuario seleccionado
- ✅ Comportamiento dinámico: solo visible para Gestor y Domicilio

#### Formulario de Editar Usuario:
- ✅ Agregada opción "Domicilio" en el select de tipo de usuario
- ✅ Agregado campo de selección múltiple para monedas asignadas
- ✅ Carga las monedas actuales del usuario al abrir el modal
- ✅ Muestra información de monedas actuales asignadas
- ✅ El campo se muestra/oculta según el tipo de usuario

#### JavaScript:
- ✅ Event listeners para mostrar/ocultar campo de monedas en crear
- ✅ Event listeners para mostrar/ocultar campo de monedas en editar
- ✅ Inicialización del estado del campo al cargar la página
- ✅ Carga de monedas asignadas al abrir modal de editar
- ✅ Envío de monedas seleccionadas al crear/editar usuario

### 2. Actualización del View `login/views.py`

#### Función `administrar_usuarios()`:
```python
# Agregado al contexto:
- monedas_disponibles: QuerySet de todas las monedas activas
```

#### Función `crear_usuario()`:
```python
# Cambios:
1. Obtiene lista de monedas asignadas: request.POST.getlist('monedas_asignadas')
2. Asigna monedas al perfil después de crear (solo para gestor y domicilio)
3. Usa perfil.monedas_asignadas.set(monedas_objetos)
```

#### Función `obtener_usuario()`:
```python
# Cambios:
1. Obtiene monedas_asignadas como lista de IDs
2. Crea monedas_asignadas_display como string con códigos separados por comas
3. Incluye ambos campos en la respuesta JSON
4. Maneja tanto administradores como otros tipos de usuario
```

#### Función `editar_usuario()`:
```python
# Cambios:
1. Obtiene lista de monedas asignadas: request.POST.getlist('monedas_asignadas')
2. Para usuarios admin:
   - Actualiza monedas si se proporcionan (admin puede tener restricciones o no)
3. Para usuarios gestor/domicilio:
   - Actualiza monedas solo si el tipo es gestor o domicilio
4. Maneja creación de perfil si no existe (con monedas)
```

## Comportamiento del Sistema

### Al Crear Usuario:

1. **Seleccionar Tipo de Usuario:**
   - **Admin** → Campo de monedas NO visible (siempre tiene acceso a todas)
   - **Contable** → Campo de monedas NO visible (siempre tiene acceso a todas)
   - **Gestor** → Campo de monedas VISIBLE (puede restringirse)
   - **Domicilio** → Campo de monedas VISIBLE (puede restringirse)

2. **Asignar Monedas (Solo Gestor/Domicilio):**
   - **Sin selección** = el usuario puede usar **todas las monedas** (comportamiento por defecto)
   - **Con selección** = el usuario solo puede usar las monedas seleccionadas
   - Mantener Ctrl (Cmd en Mac) y hacer clic para seleccionar múltiples

3. **Al Guardar:**
   - Las monedas se asignan automáticamente al perfil
   - Solo aplica para gestores y domicilios
   - Admin y contable siempre tienen acceso a todas las monedas

### Al Editar Usuario:

1. **Cargar Datos:**
   - Si el usuario es Gestor o Domicilio, el campo de monedas es visible
   - Si el usuario es Admin o Contable, el campo NO es visible
   - El modal carga las monedas actualmente asignadas (si aplica)
   - Muestra texto informativo: "Monedas actuales: USD, EUR, ..." o "Todas las monedas"
   - Las opciones asignadas aparecen pre-seleccionadas

2. **Modificar Monedas (Solo Gestor/Domicilio):**
   - Ctrl+clic para agregar/quitar monedas de la selección
   - **Deseleccionar todas** = usuario puede usar **todas las monedas**
   - Campo solo visible/editable para gestores y domicilios

3. **Al Guardar:**
   - Las monedas se actualizan en el perfil (solo para gestor/domicilio)
   - Si cambia de Gestor/Domicilio a Admin/Contable, las monedas asignadas se ignoran
   - Admin y Contable siempre acceden a todas las monedas sin restricciones

## Validaciones y Lógica de Negocio

### Restricciones por Tipo de Usuario:

| Tipo Usuario | Monedas Asignables | Comportamiento por Defecto | Campo Visible |
|--------------|-------------------|----------------------------|---------------|
| Admin        | No aplica         | Todas las monedas          | ❌ No         |
| Contable     | No aplica         | Todas las monedas          | ❌ No         |
| Gestor       | Sí                | Todas si no hay asignadas  | ✅ Sí         |
| Domicilio    | Sí                | Todas si no hay asignadas  | ✅ Sí         |

### Permisos de Acceso:

- **Admin/Contable**: Siempre acceso a todas las monedas (sin importar asignaciones)
- **Gestor/Domicilio**: 
  - Si `monedas_asignadas.count() > 0`: Solo monedas asignadas
  - Si `monedas_asignadas.count() == 0`: Todas las monedas activas

### Métodos del Modelo PerfilUsuario:

```python
# Verifica si el usuario puede usar una moneda específica
perfil.puede_usar_moneda(moneda)  # Returns: bool

# Obtiene QuerySet de monedas disponibles para el usuario
perfil.get_monedas_disponibles()  # Returns: QuerySet[Moneda]
```

## Campos del Formulario

### Crear Usuario:
```html
<select name="monedas_asignadas" multiple>
    <!-- Valor enviado: lista de IDs de monedas -->
</select>
```

### Editar Usuario:
```html
<select name="monedas_asignadas" multiple>
    <!-- Valor enviado: lista de IDs de monedas -->
    <!-- Pre-carga valores actuales del usuario -->
</select>
```

## Integración con Otras Partes del Sistema

### Próximos Pasos Recomendados:

1. **Formularios de Remesas:**
   ```python
   # En el view de crear remesa
   monedas = request.user.perfil.get_monedas_disponibles()
   form.fields['moneda'].queryset = monedas
   ```

2. **Formularios de Pagos:**
   ```python
   # En el view de crear pago
   monedas = request.user.perfil.get_monedas_disponibles()
   form.fields['tipo_moneda'].queryset = monedas
   ```

3. **Validación en Views:**
   ```python
   # Antes de crear transacción
   moneda = Moneda.objects.get(id=moneda_id)
   if not request.user.perfil.puede_usar_moneda(moneda):
       return JsonResponse({'error': 'No autorizado para esta moneda'})
   ```

## Pruebas Recomendadas

### Test 1: Crear Usuario Domicilio
1. Abrir modal "Agregar Usuario"
2. Seleccionar tipo "Domicilio"
3. Verificar que campo de monedas sea visible
4. Seleccionar USD y EUR
5. Crear usuario
6. Verificar en admin que tiene USD y EUR asignadas

### Test 2: Editar Usuario - Cambiar Tipo
1. Editar un gestor con monedas asignadas
2. Cambiar tipo a "Contable"
3. Verificar que campo de monedas se oculta
4. Guardar
5. Cambiar de vuelta a "Gestor"
6. Verificar que las monedas se mantuvieron

### Test 3: Sin Monedas Asignadas
1. Crear gestor sin seleccionar monedas
2. Verificar que puede ver todas las monedas en el sistema
3. Asignar una moneda específica
4. Verificar que ahora solo ve esa moneda

### Test 4: Usuario Domicilio - Acceso Restringido
1. Crear usuario tipo "Domicilio"
2. Asignar monedas USD y EUR
3. Iniciar sesión como ese usuario
4. Verificar acceso solo a home page
5. Intentar acceder a /remesas/ → debe redirigir a home

## Archivos Modificados

```
login/views.py
  - administrar_usuarios()      → Agregado monedas_disponibles al contexto
  - crear_usuario()             → Asignación de monedas al crear
  - obtener_usuario()           → Incluye monedas en respuesta JSON
  - editar_usuario()            → Actualización de monedas asignadas

login/templates/autenticacion/administrar_usuarios.html
  - Modal crear usuario         → Campo monedas asignadas
  - Modal editar usuario        → Campo monedas asignadas con carga de datos
  - JavaScript                  → Lógica de mostrar/ocultar y cargar monedas
```

## Notas Técnicas

### Campo Multiple Select:
- **HTML**: `<select multiple>` requiere `getlist()` en el backend
- **UX**: Ctrl+clic es estándar pero puede no ser intuitivo para usuarios
- **Alternativa futura**: Widget de checkboxes o búsqueda con tags

### Persistencia de Datos:
- Las monedas se guardan con `monedas_asignadas.set(lista)`
- Esto reemplaza completamente las asignaciones anteriores
- Lista vacía = sin asignaciones específicas = todas las monedas

### Compatibilidad:
- El código es compatible con usuarios existentes
- Usuarios sin perfil: se crea automáticamente
- Usuarios sin monedas asignadas: pueden usar todas (comportamiento por defecto)

## Soporte y Troubleshooting

### Problema: Campo de monedas no aparece
**Solución**: Verificar que `monedas_disponibles` esté en el contexto del view

### Problema: Monedas no se guardan
**Solución**: Verificar que el name del select sea `monedas_asignadas` (plural)

### Problema: Modal no carga monedas actuales
**Solución**: Verificar que `obtener_usuario()` retorne los campos `monedas_asignadas` y `monedas_asignadas_display`

### Problema: Usuario puede ver monedas no asignadas
**Solución**: Verificar implementación de `puede_usar_moneda()` en los views de transacciones
