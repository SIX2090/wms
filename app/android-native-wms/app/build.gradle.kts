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
        versionCode = 4
        versionName = "3.1.0"

        // sherpa-onnx 本地语音识别开关：通过 -Pwms.sherpa=true 启用，
        // 默认 false（保持现有国内 / 离线构建无网络依赖）。启用后会引入
        // sherpa-onnx AAR 并通过 downloadSherpaModel task 拉取模型。
        val enableSherpa = (project.findProperty("wms.sherpa") as String?)
            ?.toBooleanStrictOrNull() ?: false
        buildConfigField("boolean", "SHERPA_ENABLED", enableSherpa.toString())
        buildConfigField(
            "String",
            "SHERPA_MODEL_DIR",
            "\"${System.getenv("WMS_SHERPA_MODEL_DIR") ?: "sherpa-onnx/stream"}\""
        )
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

    // sherpa-onnx 本地离线中文语音识别：仅在 -Pwms.sherpa=true 时引入 AAR
    // （保持默认构建无网络依赖；启用后由 downloadSherpaModel 拉模型）
    if ((project.findProperty("wms.sherpa") as String?)?.toBooleanStrictOrNull() == true) {
        implementation("com.k2fsa.sherpaonnx:sherpa-onnx:1.12.13")
    }

    // DataStore (non-sensitive data)
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    // EncryptedSharedPreferences (sensitive data like token)
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Coil for image loading（2.x 网络层内置于 coil-base，用 callFactory 注入共享 OkHttpClient）
    implementation("io.coil-kt:coil-compose:2.7.0")

    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

// -----------------------------------------------------------------------------
// sherpa-onnx 模型下载任务
// -----------------------------------------------------------------------------
// 用法：
//   ./gradlew :app:downloadSherpaModel \
//     -Pwms.sherpa=true \
//     -PmodelUrl=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zh-en-2023-06-26.tar.bz2
//
// 模型下载到 app/src/main/assets/sherpa-onnx/stream/，运行时会随 APK 一起打包，
// 在国内 / 无 Google 服务的设备上提供本地离线中文识别。
// 失败时 task 不抛异常，只 warn；运行时由 SherpaVoiceSttEngine.isAvailable 检测
// 缺失并 fallback 到 AndroidVoiceSttEngine，保证 UI 不退化。
// -----------------------------------------------------------------------------
tasks.register("downloadSherpaModel") {
    group = "sherpa"
    description = "下载 sherpa-onnx 中文流式识别模型到 assets/sherpa-onnx/stream/"
    val defaultUrl =
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/" +
            "sherpa-onnx-streaming-zh-en-2023-06-26.tar.bz2"
    val modelUrl = (project.findProperty("modelUrl") as String?) ?: defaultUrl
    val targetDir = file("src/main/assets/sherpa-onnx/stream")
    val tmpFile = file("build/sherpa-model.tar.bz2")

    doLast {
        val required = listOf("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx")
        if (targetDir.isDirectory && required.all { File(targetDir, it).isFile }) {
            logger.lifecycle("sherpa-onnx model already present at $targetDir, skipping")
            return@doLast
        }
        targetDir.mkdirs()
        tmpFile.parentFile.mkdirs()
        try {
            // Gradle Kotlin DSL 中 AntBuilder 不支持 ant.invoke(mapOf(...)) 的写法；
            // 官方文档标准写法是 ant.withGroovyBuilder { "task"("attr" to value) }，
            // 多属性用 vararg Pair 展开，不是 mapOf(...) 包一层。
            ant.withGroovyBuilder {
                "get"(
                    "src" to modelUrl,
                    "dest" to tmpFile.absolutePath,
                    "verbose" to true,
                    "usetimestamp" to true
                )
            }
            ant.withGroovyBuilder {
                "bunzip2"(
                    "src" to tmpFile.absolutePath
                )
            }
            // 解 bunzip2 后通常得到 .tar
            val tarFile = File(tmpFile.parentFile, "sherpa-model.tar")
            if (tarFile.isFile) {
                ant.withGroovyBuilder {
                    "untar"(
                        "src" to tarFile.absolutePath,
                        "dest" to targetDir.absolutePath,
                        "overwrite" to true
                    )
                }
                tarFile.delete()
            }
            tmpFile.delete()
            logger.lifecycle("sherpa-onnx model downloaded to $targetDir")
        } catch (t: Throwable) {
            logger.warn(
                "downloadSherpaModel 失败：${t.message}。运行时将 fallback 到 AndroidVoiceSttEngine。"
            )
        }
    }
}