# Aplicación Android

Aplicación nativa Kotlin para Android 11 o posterior. El manifiesto registra la conexión de dispositivos USB de almacenamiento masivo. Al conectar el USB OTG, Android puede pedir que se elija Backup Imagen para abrirlo; una vez abierta, la app inicia el respaldo en un servicio en primer plano y muestra el avance y el resumen.

## Primer uso

1. Compila e instala el APK en el teléfono objetivo.
2. Abre Backup Imagen una vez y concede **Administrar todos los archivos** en los ajustes de Android.
3. Conecta por OTG el USB NTFS de 32 GB. Si Android presenta un selector de aplicaciones, elige Backup Imagen; el teléfono puede recordar esa opción.

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
- El USB de destino se identifica por su montaje NTFS y su capacidad cercana a 32 GB.
- La lista de tipos de archivo está en `AndroidBackupEngine.kt`; las copias conservan el contenido original sin conversión.
