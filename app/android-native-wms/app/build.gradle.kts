plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

android {
    namespace = "com.factory.wms"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.factory.wms"
        minSdk = 26
        targetSdk = 35
        versionCode = 3
        versionName = "3.0.0"
    }

    // 发布签名：keystore 和密码从环境变量读取，绝不上传仓库。
    // 构建前需设置：WMS_STORE_FILE, WMS_STORE_PASSWORD, WMS_KEY_ALIAS, WMS_KEY_PASSWORD
    // 注意：signingConfigs 须在 buildTypes 之前声明，否则 buildTypes 引用
    // signingConfigs.getByName("release") 时因尚未创建而报 "not found"。
    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("WMS_STORE_FILE") ?: "../keystore/wms-release.jks")
            storePassword = System.getenv("WMS_STORE_PASSWORD") ?: ""
            keyAlias = System.getenv("WMS_KEY_ALIAS") ?: "wms"
            keyPassword = System.getenv("WMS_KEY_PASSWORD") ?: ""
        }
    }

    // 发布签名校验：构建 release 时必须提供完整签名参数，缺一个即立即失败，
    // 避免用空密码/缺 alias 打出无法安装或无法更新的 APK。
    tasks.configureEach {
        if (name == "validateSigningRelease" || name == "packageRelease") {
            doFirst {
                val pwd = System.getenv("WMS_STORE_PASSWORD")
                val keyPwd = System.getenv("WMS_KEY_PASSWORD")
                val alias = System.getenv("WMS_KEY_ALIAS")
                val storeFile = System.getenv("WMS_STORE_FILE")
                if (pwd.isNullOrBlank() || keyPwd.isNullOrBlank() || alias.isNullOrBlank() || storeFile.isNullOrBlank()) {
                    throw GradleException(
                        "release 构建缺少签名参数。请设置 WMS_STORE_FILE / WMS_STORE_PASSWORD / " +
                            "WMS_KEY_ALIAS / WMS_KEY_PASSWORD（keystore 与密码绝不上传仓库）。"
                    )
                }
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-compose:1.9.3")

    // Compose UI
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.8.5")

    // Lifecycle & ViewModel
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // Retrofit
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // CameraX
    val cameraxVersion = "1.4.1"
    implementation("androidx.camera:camera-camera2:$cameraxVersion")
    implementation("androidx.camera:camera-lifecycle:$cameraxVersion")
    implementation("androidx.camera:camera-view:$cameraxVersion")

    // ML Kit Barcode Scanning
    implementation("com.google.mlkit:barcode-scanning:17.3.0")

    // DataStore (non-sensitive data)
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // EncryptedSharedPreferences (sensitive data like token)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Coil for image loading
    implementation("io.coil-kt:coil-compose:2.7.0")

    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}