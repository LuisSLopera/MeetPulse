# Compilación y distribución para Windows

## Requisitos del equipo compilador

- Windows de 64 bits.
- Python 3.11 o superior de 64 bits.
- PowerShell.

## Construcción

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,build]"
python -m pytest -q
.\scripts\build_windows.ps1
```

El script es compatible con Windows PowerShell 5.1 y PowerShell 7. Los mensajes
`INFO` de PyInstaller se muestran durante la compilación y no representan un
error; el script comprueba el código de salida real del proceso.

El script usa `assets\logo.png` con la opción `--icon`; Pillow lo convierte al
recurso de icono de Windows y PyInstaller lo incorpora en `ZoomMonitor.exe`.

Los resultados son:

```text
dist\ZoomMonitor-Windows\
dist\ZoomMonitor-Windows.zip
```

El ZIP contiene únicamente el ejecutable, `.env.example` y las instrucciones
para el usuario final. Nunca incluye `.env` ni credenciales reales.

## Equipo de destino

El equipo de destino no necesita Python. Descomprima el ZIP, copie
`.env.example` como `.env`, configure las credenciales y ejecute:

```powershell
.\ZoomMonitor.exe
```

El `.exe` no está firmado digitalmente, por lo que SmartScreen puede advertir al
usuario. Para una distribución pública se recomienda firmarlo con un certificado
de firma de código.

## Integridad

Después de compilar puede calcular el hash:

```powershell
Get-FileHash .\dist\ZoomMonitor-Windows.zip -Algorithm SHA256
```
