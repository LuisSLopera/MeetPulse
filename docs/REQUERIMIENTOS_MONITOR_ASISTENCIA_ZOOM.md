# Proyecto: Monitor automático de participantes en reuniones recurrentes de Zoom

## 1. Objetivo
Desarrollar un servicio desatendido que registre **la cantidad de participantes conectados a una reunión recurrente de Zoom cada 5 minutos**, mientras cada sesión esté activa. Debe funcionar con una cuenta Zoom Business/Enterprise y guardar un histórico confiable y exportable.

## 2. Alcance MVP
- Configurar una o varias reuniones por su Meeting ID (inicialmente una).
- Detectar automáticamente inicio y fin de cada sesión de una reunión recurrente, sin intervención del anfitrión.
- Identificar individualmente cada sesión usando su UUID, aunque reutilice Meeting ID.
- Capturar una muestra al detectar una sesión activa y después cada 300 segundos aproximadamente, medidos con reloj monotónico.
- Guardar fecha/hora UTC, fecha/hora America/Bogota, Meeting ID, UUID de sesión, número de participantes y estado de la consulta.
- Mantener historial en SQLite y exportar CSV por sesión y consolidado.
- Proveer CLI para listar sesiones, consultar muestras y exportar.
- Operar como servicio Linux systemd o contenedor Docker con reinicio automático.
- No grabar audio/video ni recolectar nombres/correos de participantes; almacenar únicamente conteos y metadatos mínimos.

## 3. Integración Zoom
- Autenticación Server-to-Server OAuth mediante Account ID, Client ID y Client Secret, leídos de variables de entorno; nunca incluir secretos en el repositorio ni logs.
- Usar endpoints oficiales de Zoom Dashboard para listar reuniones activas y consultar participantes en vivo, sujetos a permisos y plan. Verificar en la documentación vigente antes de implementar las rutas exactas, parámetros, scopes y límites.
- Referencia de partida: `GET /v2/metrics/meetings?type=live` y `GET /v2/metrics/meetings/{meetingId}/participants?type=live`. **No asumir que el endpoint, el filtro, la respuesta o el scope siguen siendo idénticos**: confirmar contra documentación oficial y prueba real.
- Considerar paginación con `next_page_token`; no contar solamente la primera página.
- Comprobar cómo Zoom representa participantes desconectados, reconexiones, anfitrión, dispositivos múltiples, salas de espera y breakout rooms. Documentar explícitamente qué significa el conteo.
- Verificar permisos de Dashboard (p. ej., scopes granulares disponibles), autorización de administrador y capacidad de consultar reuniones del anfitrión.
- Identificar UUID de sesión sin confundir reuniones recurrentes; revisar necesidad de codificar UUID en rutas de Zoom.
- Renovar tokens de forma anticipada y manejar errores 401/403, 404, 429, 5xx, timeouts y problemas de red; respetar `Retry-After` y aplicar backoff exponencial con jitter.
- No guardar una muestra de cero cuando Zoom devuelve un error, cuando no hay permisos o cuando no es posible verificar el estado.

## 4. Diseño propuesto
Python 3.11+, `httpx` o `requests`, SQLite y CLI `argparse`/`typer` (elegir lo más simple). Separar componentes:
- `zoom_client`: OAuth, peticiones, paginación, errores y rate limits.
- `session_detector`: detección de sesiones activas y UUID.
- `sampler`: planificación de muestras y control de duplicados.
- `storage`: persistencia transaccional SQLite.
- `reporting`: exportación CSV y estadísticas.
- `main`: arranque, configuración, señales SIGTERM y cierre limpio.

Modelo mínimo de datos:

**sessions**: `id`, `meeting_id`, `zoom_uuid` (único), `started_at_utc`, `last_seen_at_utc`, `ended_at_utc` nullable, `status`.

**samples**: `id`, `session_id`, `scheduled_at_utc`, `observed_at_utc`, `participant_count`, `source`, `created_at_utc`; índice único apropiado por sesión e instante programado para impedir duplicados.

**errors**: `id`, `meeting_id`, `session_uuid` nullable, `occurred_at_utc`, `operation`, `http_status` nullable, `message_sanitized`.

Guardar timestamps en UTC; convertir a `America/Bogota` para CSV/presentación. Activar WAL de SQLite y diseñar para reinicios.

## 5. Semántica del muestreo
- La primera muestra se realiza al detectar la sesión; siguientes muestras cada 300 segundos a partir de un ancla por sesión.
- Detección de reuniones activas cada 15–30 segundos, configurable. Evaluar consumo de cuota API antes de establecer valor por defecto.
- No registrar mediciones inventadas durante caídas del proceso. Los huecos deben quedar visibles.
- Registrar tanto el instante objetivo (`scheduled_at_utc`) como el instante real (`observed_at_utc`).
- Ante reinicio, reanudar sin duplicar mediciones previas; no hacer backfill ficticio.
- La sesión finaliza cuando Zoom confirma que ya no está activa; distinguir fin confirmado de indisponibilidad temporal de API.
- Si hay más de una sesión simultánea con el mismo Meeting ID, definir comportamiento seguro y registrar ambigüedad en vez de mezclar datos.

## 6. Exportación y métricas
CSV UTF-8 con encabezados: `fecha_hora_bogota,fecha_hora_utc,meeting_id,session_uuid,participantes,instante_programado_utc`.

Resumen por sesión:
- Fecha de inicio y fin (si están disponibles).
- Número de muestras válidas.
- Máximo, mínimo y promedio de los **conteos muestreados**.
- Intervalos sin datos y errores.

Aclarar que el máximo muestreado **no equivale necesariamente** al pico real entre muestras y que el promedio simple de muestras no es el número de asistentes únicos.

## 7. Configuración
Archivo `.env.example` sin secretos reales:

```dotenv
ZOOM_ACCOUNT_ID=
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_MEETING_IDS=123456789
POLL_SECONDS=20
SAMPLE_SECONDS=300
TIMEZONE=America/Bogota
DATABASE_PATH=./data/zoom_monitor.db
LOG_LEVEL=INFO
```

Validar configuración al iniciar. No solicitar ni imprimir contraseñas de Zoom ni enlaces de acceso a reuniones.

## 8. Seguridad y operación
- Ejecutar como usuario sin privilegios; permisos restrictivos para `.env` y base de datos.
- Logs estructurados sin tokens, secretos, PII ni cuerpos completos de respuestas.
- Healthcheck básico y mensajes claros cuando no se detecta sesión activa.
- Manejo correcto de SIGTERM/SIGINT.
- Documentar instalación en Ubuntu, ejemplo systemd, Dockerfile/Compose opcional, backup SQLite y rotación de logs.
- Minimizar consultas y respetar cuotas/rate limits de Zoom.

## 9. Pruebas y criterios de aceptación
1. Una sesión recurrente nueva con el mismo Meeting ID crea un registro `sessions` distinto por UUID.
2. Durante una sesión activa se guarda una primera muestra y luego una aproximadamente cada 300 segundos, sin duplicados.
3. Una sesión terminada deja de generar muestras.
4. Si hay más de 100 participantes, la paginación permite obtener el total correcto.
5. Errores HTTP o red no se guardan como conteos cero.
6. Reinicio del proceso conserva el histórico y continúa sin duplicados.
7. CSV muestra conteos, fechas y UUID correctos.
8. Secretos no aparecen en archivos versionados ni logs.
9. Pruebas unitarias con respuestas simuladas para OAuth, paginación, reuniones activas, fin de sesión, errores y reintentos.
10. Prueba de integración manual contra Zoom real con consentimiento del administrador y comparación puntual con la interfaz de participantes.

## 10. Entregables solicitados a Codex
- Código fuente ejecutable con estructura modular.
- `README.md` con requisitos de cuenta/permisos, instalación, configuración, ejecución y solución de problemas.
- `.env.example`, `.gitignore`, `requirements.txt` o `pyproject.toml`.
- Migración/creación inicial de SQLite.
- Pruebas automatizadas ejecutables sin credenciales reales.
- Archivo de servicio systemd de ejemplo; Docker opcional.
- Comandos CLI para iniciar, consultar estado, listar sesiones y exportar CSV.
- `docs/ZOOM_API_VALIDATION.md` con endpoints, scopes, límites y detalles verificados en documentación oficial, y cualquier supuesto pendiente.

## 11. Orden de desarrollo
**Fase 1 — Validación técnica:** revisar documentación oficial vigente, confirmar scopes y endpoints, probar autenticación y una consulta en vivo. Si no se dispone de credenciales, implementar mocks y dejar la validación real pendiente. No declarar integración verificada sin prueba real.

**Fase 2 — MVP:** OAuth, detección de sesiones, muestreo, SQLite, CSV y pruebas.

**Fase 3 — Producción:** systemd, robustez, logs, reintentos, documentación y pruebas de reinicio.

**Fuera de alcance inicial:** panel web, notificaciones, identificación nominal de participantes, grabaciones, informes PDF y análisis de asistencia individual.

## 12. Instrucción directa para Codex
> Implementa este proyecto de extremo a extremo siguiendo el alcance MVP y los criterios de aceptación. Primero inspecciona el repositorio y valida los supuestos de Zoom contra su documentación oficial; no inventes endpoints ni permisos. Si no tienes acceso a credenciales o a Internet, deja la integración externa claramente marcada como pendiente y crea pruebas con mocks. Prioriza simplicidad, seguridad, observabilidad y ejecución desatendida. Ejecuta las pruebas y documenta los resultados. No agregues funciones fuera del alcance sin justificación.
