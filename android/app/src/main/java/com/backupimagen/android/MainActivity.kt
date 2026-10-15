package com.backupimagen.android

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.hardware.usb.UsbConstants
import android.provider.Settings
import android.view.Gravity
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var status: TextView
    private var permissionSettingsOpened = false
    private var notificationPermissionRequested = false
    private var startedForThisConnection = false
    private var receiverRegistered = false
    private var usbPermissionPending = false
    private var usbPermissionDenied = false
    private var usbReceiverRegistered = false

    private val usbPermissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            usbPermissionPending = false
            if (intent?.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false) == true) {
                usbPermissionDenied = false
                startBackupService()
            } else {
                usbPermissionDenied = true
                status.text = "Permiso USB denegado. Desconecta y vuelve a conectar el USB para intentarlo otra vez."
            }
        }
    }

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val message = intent?.getStringExtra(BackupService.EXTRA_MESSAGE) ?: return
            val errors = intent.getStringArrayListExtra(BackupService.EXTRA_ERRORS).orEmpty()
            showStatus(message, errors)
            if (intent.action == BackupService.ACTION_FINISHED) {
                startedForThisConnection = true
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this).apply {
            textSize = 18f
            gravity = Gravity.CENTER_VERTICAL
            setPadding(28, 28, 28, 28)
            text = "Backup Imagen\n\nConecta el USB NTFS de 32 GB por OTG."
            setOnClickListener { openStoragePermissionSettings() }
        }
        setContentView(status)
        val permissionFilter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(usbPermissionReceiver, permissionFilter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(usbPermissionReceiver, permissionFilter)
        }
        usbReceiverRegistered = true
    }

    override fun onStart() {
        super.onStart()
        val filter = IntentFilter().apply {
            addAction(BackupService.ACTION_PROGRESS)
            addAction(BackupService.ACTION_FINISHED)
        }
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(statusReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(statusReceiver, filter)
        }
        receiverRegistered = true
        restoreLastStatus()
    }

    override fun onStop() {
        if (receiverRegistered) {
            unregisterReceiver(statusReceiver)
            receiverRegistered = false
        }
        super.onStop()
    }

    override fun onDestroy() {
        if (usbReceiverRegistered) {
            unregisterReceiver(usbPermissionReceiver)
            usbReceiverRegistered = false
        }
        super.onDestroy()
    }

    override fun onResume() {
        super.onResume()
        if (!Environment.isExternalStorageManager()) {
            status.text = "Concede a Backup Imagen acceso a todos los archivos para escanear el almacenamiento compartido.\n\nToca aquí para abrir el permiso."
            if (!permissionSettingsOpened) openStoragePermissionSettings()
            return
        }

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
            !notificationPermissionRequested
        ) {
            notificationPermissionRequested = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
            return
        }

        if (!startedForThisConnection) maybeStartBackup()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        startedForThisConnection = false
        usbPermissionDenied = false
        maybeStartBackup()
    }

    @Deprecated("Deprecated in Android API; retained for minSdk-compatible permission callback")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_NOTIFICATIONS) maybeStartBackup()
    }

    private fun maybeStartBackup() {
        if (startedForThisConnection || usbPermissionPending || usbPermissionDenied) return
        if (!Environment.isExternalStorageManager()) {
            status.text = "Concede a Backup Imagen acceso a todos los archivos para iniciar el respaldo."
            if (!permissionSettingsOpened) openStoragePermissionSettings()
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
            !notificationPermissionRequested
        ) {
            notificationPermissionRequested = true
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
            return
        }

        val attachedByUsb = intent?.action == ACTION_USB_DEVICE_ATTACHED
        if (!attachedByUsb && !AndroidBackupEngine.hasTargetUsb(this)) {
            status.text = "Permiso concedido.\n\nConecta el USB NTFS de 32 GB por OTG para iniciar el respaldo."
            return
        }

        val usbManager = getSystemService(UsbManager::class.java)
        val deviceFromIntent = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra<UsbDevice>(UsbManager.EXTRA_DEVICE)
        }
        val device = deviceFromIntent ?: usbManager.deviceList.values.firstOrNull(::isMassStorageDevice)
        if (device == null) {
            status.text = "Android detectó el almacenamiento, pero no expuso el dispositivo USB al sistema de permisos."
            return
        }
        if (usbManager.hasPermission(device)) {
            startBackupService()
        } else {
            requestUsbPermission(usbManager, device)
        }
    }

    private fun requestUsbPermission(manager: UsbManager, device: UsbDevice) {
        val permissionIntent = PendingIntent.getBroadcast(
            this,
            USB_PERMISSION_REQUEST,
            Intent(ACTION_USB_PERMISSION).setPackage(packageName),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        usbPermissionPending = true
        status.text = "Concede permiso de acceso al USB para iniciar el respaldo."
        try {
            manager.requestPermission(device, permissionIntent)
        } catch (error: Exception) {
            usbPermissionPending = false
            startedForThisConnection = false
            usbPermissionDenied = true
            status.text = "No se pudo solicitar acceso al USB: ${error.message}"
        }
    }

    private fun isMassStorageDevice(device: UsbDevice): Boolean =
        device.deviceClass == UsbConstants.USB_CLASS_MASS_STORAGE ||
            (0 until device.interfaceCount).any {
                device.getInterface(it).interfaceClass == UsbConstants.USB_CLASS_MASS_STORAGE
            }

    private fun startBackupService() {
        if (startedForThisConnection) return
        startedForThisConnection = true
        status.text = "USB detectado. Iniciando respaldo del almacenamiento compartido…"
        try {
            startForegroundService(Intent(this, BackupService::class.java))
        } catch (error: Exception) {
            startedForThisConnection = false
            status.text = "No se pudo iniciar el respaldo: ${error.message}"
        }
    }

    private fun openStoragePermissionSettings() {
        permissionSettingsOpened = true
        if (Build.VERSION.SDK_INT >= 30) {
            val settingsIntent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                .setData(Uri.parse("package:$packageName"))
            startActivity(settingsIntent)
        }
    }

    private fun restoreLastStatus() {
        val preferences = getSharedPreferences(BackupService.PREFERENCES_NAME, MODE_PRIVATE)
        val message = preferences.getString(BackupService.PREFERENCE_MESSAGE, null) ?: return
        val errors = preferences.getString(BackupService.PREFERENCE_ERRORS, "")
            .orEmpty()
            .split('\n')
            .filter { it.isNotBlank() }
        showStatus(message, errors)
    }

    private fun showStatus(message: String, errors: List<String>) {
        status.text = buildString {
            append(message)
            if (errors.isNotEmpty()) {
                append("\n\nDetalles:\n")
                append(errors.take(12).joinToString("\n"))
                if (errors.size > 12) append("\n... y ${errors.size - 12} errores más")
            }
        }
    }

    companion object {
        private const val ACTION_USB_DEVICE_ATTACHED = "android.hardware.usb.action.USB_DEVICE_ATTACHED"
        private const val ACTION_USB_PERMISSION = "com.backupimagen.android.USB_PERMISSION"
        private const val USB_PERMISSION_REQUEST = 42
        private const val REQUEST_NOTIFICATIONS = 41
    }
}
