package com.backupimagen.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import java.util.concurrent.Executors

class BackupService : Service() {
    private val executor = Executors.newSingleThreadExecutor()
    private val stateLock = Any()
    private val wakeLockLock = Any()
    private var running = false
    private var latestStartId = 0
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureNotificationChannel()
        startForeground(NOTIFICATION_ID, notification("Preparando el respaldo..."))
        sendUpdate(ACTION_PROGRESS, "Preparando el respaldo...")
        acquireWakeLock()
        val startWork = synchronized(stateLock) {
            latestStartId = startId
            if (running) false else {
                running = true
                true
            }
        }
        if (startWork) {
            executor.execute {
                val summary = runCatching {
                    AndroidBackupEngine(applicationContext, ::reportProgress).run()
                }.getOrElse { error ->
                    BackupSummary(0, 0, 0, 0, 1, listOf(error.message ?: "Error inesperado"))
                }
                val result = "Encontradas ${summary.discovered} | copiadas ${summary.copied} | " +
                    "omitidas ${summary.skipped} | no procesadas ${summary.failed} | " +
                    "errores de acceso ${summary.scanErrors}"
                try {
                    sendUpdate(ACTION_FINISHED, result, summary.errors)
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    getSystemService(NotificationManager::class.java)
                        .notify(NOTIFICATION_ID, completedNotification(result))
                } finally {
                    releaseWakeLock()
                    val finishedStartId = synchronized(stateLock) {
                        running = false
                        latestStartId
                    }
                    stopForeground(STOP_FOREGROUND_REMOVE)
                    stopSelf(finishedStartId)
                }
            }
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        executor.shutdownNow()
        releaseWakeLock()
        super.onDestroy()
    }

    private fun acquireWakeLock() {
        synchronized(wakeLockLock) {
            if (wakeLock?.isHeld == true) return
            wakeLock = getSystemService(PowerManager::class.java)
                .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$packageName:BackupImagen")
                .apply {
                    setReferenceCounted(false)
                    acquire()
                }
        }
    }

    private fun releaseWakeLock() {
        synchronized(wakeLockLock) {
            wakeLock?.let { lock ->
                if (lock.isHeld) lock.release()
            }
            wakeLock = null
        }
    }

    private fun reportProgress(message: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification(message))
        sendUpdate(ACTION_PROGRESS, message)
    }

    private fun sendUpdate(action: String, message: String, errors: List<String> = emptyList()) {
        getSharedPreferences(PREFERENCES_NAME, MODE_PRIVATE).edit()
            .putString(PREFERENCE_MESSAGE, message)
            .putString(PREFERENCE_ERRORS, errors.joinToString("\n"))
            .apply()
        val update = Intent(action)
            .setPackage(packageName)
            .putExtra(EXTRA_MESSAGE, message)
            .putStringArrayListExtra(EXTRA_ERRORS, ArrayList(errors))
        sendBroadcast(update)
    }

    private fun ensureNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Respaldo de imagenes", NotificationManager.IMPORTANCE_LOW),
        )
    }

    private fun notification(message: String): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Backup Imagen")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_menu_save)
            .setOngoing(true)
            .build()

    private fun completedNotification(message: String): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Backup Imagen termino")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_menu_save)
            .setAutoCancel(true)
            .build()

    companion object {
        const val ACTION_PROGRESS = "com.backupimagen.android.PROGRESS"
        const val ACTION_FINISHED = "com.backupimagen.android.FINISHED"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_ERRORS = "errors"
        const val PREFERENCES_NAME = "backup_status"
        const val PREFERENCE_MESSAGE = "message"
        const val PREFERENCE_ERRORS = "errors"
        private const val CHANNEL_ID = "backup_imagen_status"
        private const val NOTIFICATION_ID = 301
    }
}
