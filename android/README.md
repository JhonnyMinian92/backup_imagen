# Aplicación Android

Aplicación nativa Kotlin para Android 11 o posterior. El manifiesto registra la conexión de dispositivos USB de almacenamiento masivo. Al conectar el USB OTG, Android puede pedir que se elija Backup Imagen para abrirlo; una vez abierta, la app inicia el respaldo en un servicio en primer plano y muestra el avance y el resumen.

## Primer uso

1. Compila e instala el APK en el teléfono objetivo.
2. Abre Backup Imagen una vez y concede **Administrar todos los archivos** en los ajustes de Android.
3. Conecta por OTG el USB NTFS de 32 GB. Si Android presenta un selector de aplicaciones, elige Backup Imagen; acepta también el permiso del dispositivo USB si lo solicita. El teléfono puede recordar la aplicación elegida.

La app espera el montaje del USB, recorre el almacenamiento compartido y los volúmenes montados accesibles, y copia a la carpeta `backup` del USB. No lee carpetas privadas de otras aplicaciones ni archivos `.json`.

## Compilación

Se requiere Java 17 o posterior y Android SDK API 36. Desde este directorio:

```powershell
.\gradlew.bat assembleDebug
```

En Linux/macOS con Gradle Wrapper:

```bash
sh ./gradlew assembleDebug
```

El APK de depuración se genera en `app/build/outputs/apk/debug/app-debug.apk`. Instálalo con Android Studio o `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

## Acceso y privacidad

- La app no solicita permiso de Internet.
- `MANAGE_EXTERNAL_STORAGE` permite recorrer el almacenamiento compartido y el volumen USB OTG montado; Android sigue reservando los directorios privados de otras apps.
- La app lee y escribe mediante el volumen que Android monta como almacenamiento de archivos. En Android 14 o posterior solicita el permiso USB Host que el servicio en primer plano requiere; no usa la API USB para leer los archivos.
- El USB de destino debe ser extraíble, estar montado, tener capacidad cercana a 32 GB y aparecer como NTFS (`ntfs`, `ntfs3`, `ntfs-3g`, `fuse.ntfs-3g` o `fuseblk`). Algunos teléfonos informan NTFS-3G como `fuseblk`, que no permite a una app distinguir el sistema de archivos subyacente; por eso se acepta en un volumen extraíble que cumpla el montaje y la capacidad esperados. Usa aquí únicamente el USB NTFS confirmado para este producto.
- La lista de tipos de archivo está en `AndroidBackupEngine.kt`; las copias conservan el contenido original sin conversión.
