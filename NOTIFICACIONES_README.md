# Sistema de Notificaciones WhatsApp para EGLIS

Este sistema envía notificaciones automáticas por WhatsApp cuando:
- Se crea una nueva remesa
- Se crea un nuevo pago
- Cambia el estado de una remesa

## 🚀 Configuración Rápida

### Opción 1: WhatsApp Business API (Meta) - GRATIS y RECOMENDADO

1. **Configurar Meta Business:**
   - Ve a https://developers.facebook.com/
   - Crea una app para "WhatsApp Business Platform"
   - Obtén tu token de acceso y Phone Number ID
   - Es GRATIS para desarrollo y pruebas

2. **Configurar en EGLIS:**
   ```bash
   python manage.py setup_notificaciones \
     --whatsapp-token "tu_token_de_meta" \
     --whatsapp-phone-id "tu_phone_id" \
     --add-destinatario "Admin Principal" "+5358270033" \
     --activar
   ```

3. **Probar configuración:**
   ```bash
   python manage.py setup_notificaciones --test "+5358270033"
   ```

### Opción 2: Usando Twilio (Alternativo)

1. **Crear cuenta en Twilio:**
   - Ve a https://www.twilio.com/
   - Crea una cuenta gratuita
   - Activa WhatsApp Business en tu cuenta

2. **Obtener credenciales:**
   - Account SID (empieza con "AC...")
   - Auth Token
   - Número de WhatsApp Business

3. **Configurar en EGLIS:**
   ```bash
   python manage.py setup_notificaciones \
     --twilio-sid "ACxxxxxxxxxxxxxxxxx" \
     --twilio-token "tu_auth_token" \
     --twilio-phone "+14155551234" \
     --add-destinatario "Admin Principal" "+5358270033" \
     --activar
   ```

4. **Probar configuración:**
   ```bash
   python manage.py setup_notificaciones --test "+5358270033"
   ```

### Opción 3: CallMeBot API - SÚPER FÁCIL y GRATIS

1. **Configurar CallMeBot (GRATIS):**
   - Ve a https://www.callmebot.com/blog/free-api-whatsapp-messages/
   - Envía "I allow callmebot to send me messages" al número de WhatsApp: **+34 644 84 44 84**
   - Recibirás tu API Key personalizada
   - ¡Es 100% gratis y sin registro!

2. **Configurar en EGLIS:**
   ```bash
   # Agregar a la configuración manualmente desde el panel web
   # Ve a /notificaciones/configuracion/
   # O usa el panel admin: /admin/notificaciones/
   ```

3. **Es la opción MÁS SIMPLE:**
   - No requiere registro complicado
   - No requiere verificación de dominio
   - Funciona inmediatamente
   - 100% gratuito

## 📱 Formato de Números

- **Correcto:** `+1234567890` (con código de país)
- **Incorrecto:** `1234567890` (sin código de país)

## 🛠️ Gestión desde Panel Admin

### Acceso rápido:
- **Configuración:** `/notificaciones/configuracion/`
- **Destinatarios:** `/notificaciones/destinatarios/`
- **Historial:** `/notificaciones/logs/`
- **Panel Admin:** `/admin/notificaciones/`

### Funciones del panel:
- ✅ Configurar APIs (Twilio/WhatsApp Business)
- ✅ Gestionar destinatarios
- ✅ Ver historial de notificaciones
- ✅ Probar conexión
- ✅ Enviar mensajes de prueba

## 📋 Tipos de Notificaciones

### Nueva Remesa:
```
🚀 NUEVA REMESA CREADA

📋 ID: REM-2025-123456
👤 Gestor: Juan Pérez
💰 Importe: $500.00 USD
📅 Fecha: 03/08/2025 14:30
📞 Receptor: María García
🎯 Destinatario: Carlos López
📊 Estado: Pendiente

Sistema EGLIS - Notificación automática
```

### Nuevo Pago:
```
💳 NUEVO PAGO CREADO

👤 Usuario: Ana Rodríguez
💰 Cantidad: $200.00 USD
💳 Tipo: Transferencia
🎯 Destinatario: Luis Martín
📞 Teléfono: +1234567890
📅 Fecha: 03/08/2025 14:30

Sistema EGLIS - Notificación automática
```

### Cambio de Estado:
```
🔄 CAMBIO DE ESTADO - REMESA

📋 ID: REM-2025-123456
👤 Gestor: Juan Pérez
💰 Importe: $500.00 USD
📊 Estado anterior: Pendiente
✅ Estado actual: Confirmada
📅 Actualizado: 03/08/2025 15:00

Sistema EGLIS - Notificación automática
```

## 🔧 Comandos Útiles

### Ver estado del sistema:
```bash
python manage.py setup_notificaciones
```

### Agregar destinatario:
```bash
python manage.py setup_notificaciones --add-destinatario "Nombre" "+1234567890"
```

### Activar notificaciones:
```bash
python manage.py setup_notificaciones --activar
```

### Enviar mensaje de prueba:
```bash
python manage.py setup_notificaciones --test "+1234567890"
```

## 🏗️ Estructura del Sistema

```
notificaciones/
├── models.py              # Modelos de configuración y logs
├── services.py            # Servicio principal de WhatsApp
├── signals.py             # Señales automáticas
├── admin.py               # Panel de administración
├── views.py               # Vistas web
├── forms.py               # Formularios
├── urls.py                # URLs
└── management/commands/
    └── setup_notificaciones.py  # Comando de configuración
```

## 🔒 Seguridad

- Las credenciales se almacenan encriptadas en la base de datos
- Los tokens de API nunca se muestran en logs
- Solo usuarios administradores pueden configurar el sistema

## 📊 Monitoreo

El sistema registra:
- ✅ Notificaciones enviadas exitosamente
- ❌ Errores en el envío
- 📱 Respuestas de las APIs
- ⏰ Timestamps de todos los eventos

## 🆘 Solución de Problemas

### Error: "No hay configuración válida de API"
- Verifica que hayas configurado Twilio o WhatsApp Business API
- Usa el comando `--test` para probar la conexión

### Error: "Invalid phone number"
- Asegúrate de incluir el código de país (+)
- Formato correcto: +1234567890

### No se envían notificaciones:
- Verifica que el sistema esté activo
- Revisa que los destinatarios estén activos
- Comprueba los logs en `/admin/notificaciones/lognotificacion/`

## 📞 Contacto y Soporte

Para soporte técnico, revisa los logs en:
- Panel admin: `/admin/notificaciones/lognotificacion/`
- Vista web: `/notificaciones/logs/`
