plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.backupimagen.android"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.backupimagen.android"
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }
}
