# Backup Imagen

Respaldo local de imágenes desde un PC Windows/Linux o un teléfono Android hacia un USB NTFS de 32 GB. Al conectar el USB, el monitor del equipo inicia el respaldo; la consola o pantalla de estado presenta el resultado. Durante el respaldo no se usa Internet ni se suben archivos.

## Comportamiento

- El destino es siempre la carpeta `backup` en la raíz del USB.
- Se conserva el nombre y la ruta relativa de cada archivo. En PC, cada unidad de origen se identifica por su letra dentro de `backup` (`backup/C/...`, `backup/D/...`). En Android se conserva cada almacenamiento bajo una etiqueta (`backup/Interno/...`).
- Se copian los archivos como están; no se convierten ni modifican los originales.
- Si el archivo de destino tiene el mismo contenido, se omite. Si coincide el nombre pero el contenido es distinto, se crea `nombre (copia 1).ext`, incrementando el sufijo si hace falta.
- Se publica cada copia cuando termina. Un error de archivo o carpeta se registra y el recorrido continúa cuando es seguro.
- Al final se informa cuántas imágenes encontró, copió, omitió y no pudo procesar.

## Formatos incluidos

JPG/JPEG, PNG, WebP, AVIF, GIF, TIFF/TIF, RAW y variantes de cámaras, BMP, HEIC/HEIF, ICO, SVG, AI, EPS, CDR, PSD, PSB y PDF. La detección se realiza por extensión y conserva los bytes originales. Lottie y los archivos `.json` no se copian.

## USB de destino

El programa reconoce memorias NTFS con una capacidad aproximada de 32 GB. FAT32 no forma parte del destino admitido. El monitor no escribe en una ruta local cuando falta el USB.

## PC Windows

Requiere Python 3.10 o posterior. Ejecuta PowerShell desde la carpeta del proyecto y registra el monitor para que se inicie al iniciar sesión:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows-watcher.ps1
```

Después de iniciar sesión, conecta el USB NTFS de 32 GB. Se abrirá una consola que recorre las unidades fijas y extraíbles accesibles, excluye el USB de destino y muestra el resumen. Para quitar el monitor:

```powershell
.\scripts\uninstall-windows-watcher.ps1
```

## PC Linux

Requiere Python 3.10 o posterior, `python3-venv`, systemd de usuario y una terminal gráfica. El instalador crea un entorno Python aislado y registra el monitor con:

```bash
sh scripts/install-linux-watcher.sh
```

Al iniciar la sesión, el monitor detecta un volumen NTFS de aproximadamente 32 GB y abre la terminal disponible. Para desinstalarlo:

```bash
sh scripts/uninstall-linux-watcher.sh
```

## Android

La app nativa y sus instrucciones de compilación/instalación están en [`android/README.md`](android/README.md). En el primer uso, Android solicita el permiso de acceso amplio al almacenamiento compartido. El teléfono debe permitir el acceso OTG al USB NTFS confirmado para ese modelo.

Android no permite leer las carpetas privadas de otras aplicaciones. El respaldo recorre el almacenamiento compartido y los volúmenes montados accesibles para la app.

## Desarrollo y compilación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
python -m ruff check .
```

Para compilar Android en Windows:

```powershell
cd android
.\gradlew.bat assembleDebug
```

El APK de depuración queda en `android/app/build/outputs/apk/debug/app-debug.apk`.

## Límites

- El sistema operativo determina qué carpetas son accesibles. En PC, carpetas protegidas pueden registrarse como no procesadas.
- El destino debe ser un volumen NTFS montado con capacidad cercana a 32 GB. El espacio libre real depende de los archivos que ya tenga.
- Antes del uso diario, valida el flujo en el PC y los teléfonos objetivo conectados al USB físico.
