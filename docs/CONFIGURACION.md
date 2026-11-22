# Configuración

## Aplicación de Zoom

Cree una aplicación **Server-to-Server OAuth** en Zoom Marketplace. Debe estar
activa y contar con estos scopes granulares:

```text
meeting:read:meeting:admin
dashboard:read:list_meetings:admin
dashboard:read:list_meeting_participants:admin
```

Después de cambiar scopes, guarde y reactive la aplicación para que los nuevos
tokens los incluyan.

## Variables de entorno

Copie `.env.example` como `.env`. Este último contiene secretos y está excluido
de Git.

| Variable | Obligatoria | Descripción |
|---|---:|---|
| `ZOOM_ACCOUNT_ID` | Sí | Account ID de la aplicación S2S. |
| `ZOOM_CLIENT_ID` | Sí | Client ID de la aplicación S2S. |
| `ZOOM_CLIENT_SECRET` | Sí | Secreto; no debe compartirse ni versionarse. |
| `ZOOM_MEETING_IDS` | Sí | IDs separados por comas, en el orden del menú. |
| `POLL_SECONDS` | No | Frecuencia para detectar inicio/fin; predeterminado `20`. |
| `SAMPLE_SECONDS` | No | Intervalo de muestras; predeterminado `300`. |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING` o `ERROR`. |
| `ZOOM_REQUEST_TIMEOUT` | No | Timeout HTTP; predeterminado `20`. |
| `ZOOM_MAX_RETRIES` | No | Reintentos para fallos temporales; predeterminado `4`. |

Valide la configuración con:

```powershell
.\ZoomMonitor.exe validate
```

En desarrollo use `zoom-monitor validate`.

## Solución de problemas

- `401`: revise las tres credenciales de la aplicación S2S.
- `403` o mensaje de scope: agregue el scope indicado y reactive la app.
- La reunión no aparece activa: confirme el Meeting ID y espere hasta que Zoom
  Dashboard la publique.
- El conteo puede tardar brevemente en reflejar cambios de Zoom. Se excluyen
  conexiones con `leave_time` y usuarios en sala de espera.
- No se escribe una muestra de cero cuando la API falla; el programa reintenta.
