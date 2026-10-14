# Aplicación Android

La aplicación Android nativa se implementará en una fase separada con Kotlin y Android Storage Access Framework.

Requisitos de diseño:
- Solicitar al usuario que seleccione la carpeta o unidad USB mediante el selector del sistema.
- Usar permisos concedidos explícitamente por el usuario y conservar el acceso solo cuando Android lo permita.
- No intentar eludir el sandbox ni acceder a carpetas privadas de otras aplicaciones.
- No asumir que todos los teléfonos montan NTFS/exFAT/FAT32 del mismo modo.
- Permitir iniciar el respaldo manualmente; Android no garantiza ejecutar una aplicación al conectar cualquier USB.
- Mantener el motor sin red y sin telemetría.

Este directorio aún no contiene un APK ni una aplicación compilable.
