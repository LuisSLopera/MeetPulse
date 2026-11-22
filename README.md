# Monitor de participantes Zoom

Programa interactivo de línea de comandos. Lee varios Meeting ID desde `.env`,
consulta sus nombres en Zoom, muestra un menú y guarda cada ejecución en un CSV
independiente compatible con Excel.

## Configuración

Requiere Python 3.11 o superior y una app Zoom Server-to-Server OAuth activa.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
notepad .env
```

Configure los IDs separados por comas:

```dotenv
ZOOM_ACCOUNT_ID=...
ZOOM_CLIENT_ID=...
ZOOM_CLIENT_SECRET=...
ZOOM_MEETING_IDS=85965372631,12345678901
POLL_SECONDS=20
SAMPLE_SECONDS=300
LOG_LEVEL=INFO
```

Scopes granulares requeridos:

```text
meeting:read:meeting:admin
dashboard:read:list_meetings:admin
dashboard:read:list_meeting_participants:admin
```

Después de agregar scopes hay que guardar y reactivar la app en Zoom Marketplace.
La referencia completa de variables y diagnóstico está en
[`docs/CONFIGURACION.md`](docs/CONFIGURACION.md).

## Ejecución

```powershell
zoom-monitor
```

Ejemplo:

```text
Reuniones configuradas:

  1. Evangelización mundial (ID: 85965372631)
  2. Reunión de líderes (ID: 12345678901)
  0. Salir

Seleccione la reunion que desea monitorear:
```

Al elegir una reunión, el programa espera hasta que esté activa, registra una
muestra inmediata y después una cada `SAMPLE_SECONDS`. Presione `Ctrl+C` para
detenerlo. También finaliza cuando Zoom confirma que terminó la reunión.

Cada ejecución crea `exports/reunion_ID_FECHA_HORA.csv`. Usa punto y coma (`;`):

```text
fecha;hora;meeting_id;nombre_reunion;participantes;estado
```

`fecha` usa `AAAA-MM-DD`; `hora` usa `HH:MM:SS` y corresponde a la hora local del
equipo. No se almacenan UUID, nombres, correos ni datos personales de participantes.

Para comprobar credenciales, scopes e IDs:

```powershell
zoom-monitor validate
```

## Pruebas

```powershell
python -m pytest -q
```

## Ejecutable para Windows

El proyecto incluye un script que genera un `.exe` autocontenido:

```powershell
python -m pip install -e ".[build]"
.\scripts\build_windows.ps1
```

El paquete para copiar a otro equipo queda en `dist\ZoomMonitor-Windows`. El
equipo de destino no necesita Python; sólo debe crear su `.env` a partir de
`.env.example` y ejecutar `ZoomMonitor.exe`.

El ejecutable usa `assets\logo.png` como icono. PyInstaller lo convierte al
formato requerido por Windows durante la compilación.

Consulte el procedimiento completo en
[`docs/COMPILACION_WINDOWS.md`](docs/COMPILACION_WINDOWS.md).

## Estructura del proyecto

```text
assets/                  Recursos visuales (logo.png)
docs/                    Requisitos e instrucciones de distribución
scripts/                 Entrada y compilación para Windows
src/zoom_monitor/        Código fuente
tests/                   Pruebas automatizadas
.env.example             Plantilla sin secretos
pyproject.toml           Dependencias y configuración del paquete
README.md                Documentación principal
```

## Seguridad y archivos generados

- `.env`, exportaciones CSV, bases locales, logs, entornos virtuales, caches y
  artefactos de compilación están excluidos mediante `.gitignore`.
- `.env.example` sí se versiona y nunca debe contener credenciales reales.
- Los CSV se crean en `exports/` y no contienen nombres ni correos de asistentes.
- El ZIP de distribución nunca incorpora el `.env` real.
