package com.backupimagen.android

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.view.Gravity
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var status: TextView
    private var permissionSettingsOpened = false
    private var notificationPermissionRequested = false
    private var startedForThisConnection = false
    private var receiverRegistered = false
    private var usbPermissionReceiverRegistered = false
    private var usbPermissionRequested = false
    private var usbPermissionDenied = false

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

    private val usbPermissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != ACTION_USB_PERMISSION) return
            usbPermissionRequested = false
            val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
            if (granted) {
                usbPermissionDenied = false
                maybeStartBackup()
            } else {
                usbPermissionDenied = true
                status.text = "Se necesita permiso para el USB. Desconéctalo y vuelve a conectarlo para intentarlo de nuevo."
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

        val usbFilter = IntentFilter(ACTION_USB_PERMISSION)
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(usbPermissionReceiver, usbFilter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            registerReceiver(usbPermissionReceiver, usbFilter)
        }
        usbPermissionReceiverRegistered = true
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
        if (usbPermissionReceiverRegistered) {
            unregisterReceiver(usbPermissionReceiver)
            usbPermissionReceiverRegistered = false
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
        usbPermissionRequested = false
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
        if (startedForThisConnection) return
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
        val hasMountedTarget = AndroidBackupEngine.hasTargetUsb(this)
        if (!attachedByUsb && !hasMountedTarget) {
            status.text = "Permiso concedido.\n\nConecta el USB NTFS de 32 GB por OTG para iniciar el respaldo."
            return
        }

        if (Build.VERSION.SDK_INT >= 34) {
            if (usbPermissionDenied || usbPermissionRequested) return
            val usbManager = getSystemService(UsbManager::class.java)
            val attachedDevice = usbDeviceFromIntent(intent)
            val device = attachedDevice ?: usbManager.deviceList.values.firstOrNull(::isUsbStorageDevice)
            if (device == null) {
                status.text = "Android no expone el dispositivo USB necesario para iniciar el respaldo. Desconecta y vuelve a conectar el USB OTG."
                return
            }
            if (!usbManager.hasPermission(device)) {
                requestUsbPermission(usbManager, device)
                return
            }
        }

        startBackupService()
    }

    private fun requestUsbPermission(usbManager: UsbManager, device: UsbDevice) {
        usbPermissionRequested = true
        status.text = "Autoriza el acceso al dispositivo USB para iniciar el respaldo."
        val permissionIntent = PendingIntent.getBroadcast(
            this,
            USB_PERMISSION_REQUEST,
            Intent(ACTION_USB_PERMISSION)
                .setPackage(packageName)
                .setData(Uri.parse("backup-imagen://usb-permission/${device.deviceId}")),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        try {
            usbManager.requestPermission(device, permissionIntent)
        } catch (error: Exception) {
            usbPermissionRequested = false
            status.text = "No se pudo solicitar permiso para el USB: ${error.message}"
        }
    }

    private fun usbDeviceFromIntent(intent: Intent?): UsbDevice? {
        if (intent?.action != ACTION_USB_DEVICE_ATTACHED) return null
        return if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra<UsbDevice>(UsbManager.EXTRA_DEVICE)
        }
    }

    private fun isUsbStorageDevice(device: UsbDevice): Boolean =
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
