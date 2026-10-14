# Backup Imagen

Herramienta local para respaldar fotografías e imágenes desde equipos Windows, Linux y Android hacia una memoria USB.

## Estado del proyecto

Desarrollo inicial. El motor de escritorio se está construyendo primero; la aplicación Android nativa y los paquetes distribuibles se incorporarán en fases posteriores. No se considera listo para uso real hasta completar las pruebas en equipos y sistemas de archivos físicos.

## Principios

- Copiar, nunca borrar ni modificar los archivos originales.
- No sobrescribir archivos existentes en el destino.
- Conservar la estructura relativa de carpetas.
- Si un nombre ya existe con contenido distinto, crear un nombre alternativo.
- Copiar a un archivo temporal y publicarlo cuando la copia termine correctamente.
- Informar de los errores por archivo y continuar cuando sea seguro.
- No usar Internet durante los respaldos ni subir datos.

## Plataformas previstas

- Windows y Linux: aplicación de consola en Python.
- Android: aplicación nativa Kotlin, con permisos explícitos mediante las APIs de almacenamiento de Android y acceso OTG cuando el dispositivo lo permita.

La compatibilidad con NTFS, FAT32 y exFAT depende del sistema operativo, sus controladores y el dispositivo. FAT32 no admite archivos individuales de 4 GiB o más.

## Desarrollo

Requisitos iniciales: Python 3.10 o superior y pytest para ejecutar las pruebas.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Ejemplo de uso del motor:

```bash
python -m backup_imagen --source "/ruta/imagenes" --destination "/ruta/USB/backup" --device-name "ANDROID-01"
```

En Windows, sustituye las rutas por rutas válidas del sistema, por ejemplo `E:\\backup`.

## Estructura

- `src/backup_imagen/`: motor de copia y CLI.
- `tests/`: pruebas automatizadas.
- `android/`: aplicación nativa Android (fase posterior).

## Limitaciones actuales

- La versión inicial del motor trabaja sobre una carpeta de origen que el usuario especifica; todavía no descubre automáticamente todos los discos ni tiene integración Android.
- Los formatos se detectan por extensión; no se convierten ni se decodifican las imágenes.
- El programa no puede acceder a carpetas protegidas o privadas sin autorización del sistema operativo.
- El arranque automático desde USB no está garantizado y se evitará cualquier mecanismo que el sistema operativo bloquee por seguridad.
