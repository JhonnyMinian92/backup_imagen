package com.backupimagen.android

import android.content.Context
import android.os.Environment
import android.os.StatFs
import android.os.storage.StorageManager
import android.os.storage.StorageVolume
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.file.FileAlreadyExistsException
import java.nio.file.Files
import java.nio.file.LinkOption
import java.util.ArrayDeque
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID

internal data class BackupSummary(
    val discovered: Int,
    val copied: Int,
    val skipped: Int,
    val failed: Int,
    val scanErrors: Int,
    val errors: List<String>,
)

internal class AndroidBackupEngine(
    private val context: Context,
    private val onProgress: (String) -> Unit,
) {
    private data class SourceRoot(val directory: File, val label: String)

    private val extensions = setOf(
        "jpg", "jpeg", "jpe", "jfif", "jif", "jfi", "png", "webp", "avif", "avifs", "gif", "tif", "tiff",
        "raw", "dng", "cr2", "cr3", "crw", "nef", "nrw", "arw", "srf", "sraf", "sr2",
        "orf", "rw2", "raf", "pef", "3fr", "iiq", "kdc", "dcr", "mos",
        "mrw", "x3f", "erf", "mef", "rwl", "srw", "ari", "bay", "cap",
        "dcs", "drf", "eip", "fff", "gpr", "k25", "mdc", "obm", "ptx",
        "pxn", "r3d", "rwz", "bmp", "dib",
        "heic", "heics", "heif", "heifs", "hif", "ico", "svg", "svgz", "ai",
        "eps", "epsf", "epsi", "cdr", "psd", "psb", "pdf",
    )

    private val errors = mutableListOf<String>()
    private var discovered = 0
    private var copied = 0
    private var skipped = 0
    private var failed = 0
    private var scanErrors = 0

    fun run(): BackupSummary {
        if (!Environment.isExternalStorageManager()) {
            return failure("Falta conceder el permiso de acceso a todos los archivos.")
        }

        val storageManager = context.getSystemService(StorageManager::class.java)
        fun mountedVolumes(): List<Pair<StorageVolume, File>> = storageManager.storageVolumes
            .filter { it.state == Environment.MEDIA_MOUNTED }
            .mapNotNull { volume -> runCatching { volume.directory?.let { volume to it } }.getOrNull() }

        var volumes = mountedVolumes()
        var destinationVolume = volumes.firstOrNull { (volume, directory) ->
            volume.isRemovable && isTargetUsb(volume, directory)
        }
        for (attempt in 1..30) {
            if (destinationVolume != null) break
            onProgress("Esperando el montaje del USB OTG… ($attempt/30)")
            Thread.sleep(1_000)
            volumes = mountedVolumes()
            destinationVolume = volumes.firstOrNull { (volume, directory) ->
                volume.isRemovable && isTargetUsb(volume, directory)
            }
        }
        val selectedDestination = destinationVolume
            ?: return failure("No se encontro un USB NTFS de 32 GB montado por OTG.")

        val target = selectedDestination.second.toPath().toAbsolutePath().normalize().toFile()
        if (!target.isDirectory || !target.canWrite()) {
            return failure("Android no permite escribir en el USB: $target")
        }
        try {
            ensureTargetDirectory(target, File(target, "backup"))
        } catch (error: Exception) {
            return failure("No se pudo preparar la carpeta backup: ${error.message}")
        }

        val sourceRoots = volumes
            .mapNotNull { (volume, directory) ->
                val sourceDirectory = directory.toPath().toAbsolutePath().normalize().toFile()
                if (isAtOrBelow(sourceDirectory, target)) return@mapNotNull null
                val label = if (volume.isRemovable) {
                    safeLabel("${volume.getDescription(context)}_${volume.uuid ?: directory.name}")
                } else {
                    "Interno"
                }
                SourceRoot(sourceDirectory, label)
            }
            .distinctBy { it.directory.toPath().normalize() }

        if (sourceRoots.isEmpty()) {
            return failure("No se encontraron almacenamientos de origen accesibles.")
        }

        onProgress("Escaneando el almacenamiento del telefono…")
        for (root in sourceRoots) {
            if (!root.directory.exists() || !root.directory.isDirectory) {
                scanError("${root.directory}: no se puede recorrer el almacenamiento")
                continue
            }
            try {
                scanDirectory(root, target)
            } catch (error: Exception) {
                scanError("${root.directory.path}: ${error.message ?: error.javaClass.simpleName}")
            }
        }
        onProgress("Respaldo terminado.")
        return summary()
    }

    private fun scanDirectory(root: SourceRoot, target: File) {
        val pending = ArrayDeque<File>()
        pending.addLast(root.directory)
        while (pending.isNotEmpty()) {
            val directory = pending.removeLast()
            if (isAtOrBelow(directory, target) || Files.isSymbolicLink(directory.toPath())) continue
            if (isPrivateAndroidDirectory(directory)) {
                scanError("${directory.path}: Android reserva esta carpeta para datos privados de apps")
                continue
            }

            val entries = directory.listFiles()
            if (entries == null) {
                scanError("${directory.path}: Android no permitio leer esta carpeta")
                continue
            }
            for (entry in entries.sortedByDescending { it.name.lowercase(Locale.ROOT) }) {
                try {
                    if (isAtOrBelow(entry, target) || Files.isSymbolicLink(entry.toPath())) continue
                    if (entry.isDirectory) {
                        pending.addLast(entry)
                    } else if (entry.isFile && entry.extension.lowercase(Locale.ROOT) in extensions) {
                        discovered++
                        try {
                            copyOne(entry, root, target)
                        } catch (error: Exception) {
                            failFile("${entry.path}: ${error.message ?: error.javaClass.simpleName}")
                        }
                        if (discovered % 25 == 0) {
                            onProgress(
                                "Encontradas $discovered · copiadas $copied · " +
                                    "omitidas $skipped · no procesadas $failed · " +
                                    "errores de acceso $scanErrors",
                            )
                        }
                    }
                } catch (error: Exception) {
                    scanError("${entry.path}: ${error.message ?: error.javaClass.simpleName}")
                }
            }
        }
    }

    private fun isPrivateAndroidDirectory(directory: File): Boolean =
        directory.parentFile?.name == "Android" && directory.name in setOf("data", "obb")

    private fun isAtOrBelow(path: File, root: File): Boolean {
        val candidatePath = path.toPath().toAbsolutePath().normalize()
        val rootPath = root.toPath().toAbsolutePath().normalize()
        return candidatePath.startsWith(rootPath)
    }

    private fun ensureTargetDirectory(root: File, directory: File) {
        val rootPath = root.toPath().toAbsolutePath().normalize()
        val directoryPath = directory.toPath().toAbsolutePath().normalize()
        if (!directoryPath.startsWith(rootPath)) {
            throw IllegalArgumentException("La carpeta de respaldo sale del USB")
        }
        var current = root
        for (part in rootPath.relativize(directoryPath)) {
            current = File(current, part.toString())
            if (Files.isSymbolicLink(current.toPath())) {
                throw IllegalArgumentException("La ruta contiene un enlace simbolico: $current")
            }
            if (!current.exists() && !current.mkdir() && !current.isDirectory) {
                throw IllegalStateException("No se pudo crear ${current.path}")
            }
            if (!current.isDirectory) {
                throw IllegalArgumentException("La ruta no es una carpeta: $current")
            }
        }
    }

    private fun copyOne(source: File, root: SourceRoot, target: File) {
        val sourcePath = source.toPath().toAbsolutePath().normalize()
        val rootPath = root.directory.toPath().toAbsolutePath().normalize()
        val relative = rootPath.relativize(sourcePath)
        var targetDirectory = File(target, "backup/${root.label}")
        relative.parent?.forEach { segment -> targetDirectory = File(targetDirectory, segment.toString()) }
        ensureTargetDirectory(target, targetDirectory)

        val original = File(targetDirectory, source.name)
        var output = availableTarget(original, source)
        while (output != null) {
            try {
                copyAtomically(source, output)
                copied++
                return
            } catch (_: FileAlreadyExistsException) {
                output = availableTarget(original, source)
            }
        }
        skipped++
    }

    private fun availableTarget(original: File, source: File): File? {
        if (!existsWithoutFollowingLinks(original)) return original
        if (sameContent(original, source)) return null

        val dot = original.name.lastIndexOf('.')
        val stem = if (dot > 0) original.name.substring(0, dot) else original.name
        val suffix = if (dot > 0) original.name.substring(dot) else ""
        var index = 1
        while (true) {
            val candidate = File(original.parentFile, "$stem (copia $index)$suffix")
            if (!existsWithoutFollowingLinks(candidate)) return candidate
            if (sameContent(candidate, source)) return null
            index++
        }
    }

    private fun copyAtomically(source: File, target: File) {
        val temporary = File(target.parentFile, ".${target.name}.${UUID.randomUUID()}.backup-imagen-tmp")
        try {
            FileInputStream(source).use { input ->
                FileOutputStream(temporary, false).use { output ->
                    input.copyTo(output, DEFAULT_BUFFER_SIZE * 16)
                    output.fd.sync()
                }
            }
            Files.move(temporary.toPath(), target.toPath())
        } finally {
            temporary.delete()
        }
    }

    private fun existsWithoutFollowingLinks(file: File): Boolean =
        Files.exists(file.toPath(), LinkOption.NOFOLLOW_LINKS)

    private fun sameContent(first: File, second: File): Boolean {
        if (Files.isSymbolicLink(first.toPath())) return false
        if (!first.isFile || first.length() != second.length()) return false
        return digest(first).contentEquals(digest(second))
    }

    private fun digest(file: File): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE * 16)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest()
    }

    private fun isTargetUsb(volume: StorageVolume, directory: File): Boolean {
        return isTargetNtfsVolume(volume, directory)
    }

    private fun safeLabel(value: String): String = value
        .trim()
        .replace(Regex("[<>:\"/\\\\|?*\\p{Cntrl}]"), "_")
        .trimEnd('.', ' ')
        .ifBlank { "Almacenamiento" }

    private fun failFile(message: String) {
        failed++
        recordError(message)
    }

    private fun scanError(message: String) {
        scanErrors++
        recordError(message)
    }

    private fun recordError(message: String) {
        if (errors.size < MAX_REPORTED_ERRORS) errors += message
    }

    private fun failure(message: String): BackupSummary {
        scanError(message)
        return summary()
    }

    private fun summary() = BackupSummary(discovered, copied, skipped, failed, scanErrors, errors.toList())

    companion object {
        private const val MAX_REPORTED_ERRORS = 100
        private const val USB_MIN_BYTES = 28_000_000_000L
        private const val USB_MAX_BYTES = 36_000_000_000L

        fun hasTargetUsb(context: Context): Boolean {
            val manager = context.getSystemService(StorageManager::class.java)
            return manager.storageVolumes.any { volume ->
                val directory = volume.directory
                volume.isRemovable && volume.state == Environment.MEDIA_MOUNTED &&
                    directory != null && isTargetNtfsVolume(volume, directory)
            }
        }

        private fun isTargetNtfsVolume(volume: StorageVolume, directory: File): Boolean {
            val totalBytes = runCatching { StatFs(directory.path).totalBytes }.getOrDefault(0L)
            if (totalBytes !in USB_MIN_BYTES..USB_MAX_BYTES || !directory.canWrite()) return false

            val pathKey = (volume.uuid ?: directory.name).lowercase(Locale.ROOT)
            val targetPath = directory.toPath().toAbsolutePath().normalize().toString().trimEnd('/')
                .lowercase(Locale.ROOT)
            val supportedFilesystems = setOf("ntfs", "ntfs3", "ntfs-3g", "fuse.ntfs-3g", "fuseblk")
            val mounts = runCatching { File("/proc/mounts").readLines() }.getOrDefault(emptyList())
            return mounts.any { line ->
                val columns = line.split(Regex("\\s+"))
                val filesystem = columns.getOrNull(2)?.lowercase(Locale.ROOT)
                if (filesystem == null || filesystem !in supportedFilesystems) {
                    return@any false
                }
                val mountField = columns.getOrNull(1) ?: return@any false
                val mountPath = Regex("\\\\([0-7]{3})").replace(mountField) { match ->
                    match.groupValues[1].toInt(8).toChar().toString()
                }.lowercase(Locale.ROOT).trimEnd('/')
                mountPath == targetPath || mountPath.substringAfterLast('/') == pathKey
            }
        }
    }
}
