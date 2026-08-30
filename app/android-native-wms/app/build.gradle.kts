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
        versionCode = 9
        versionName = "3.5.1"

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
        // 登录页默认服务器地址：构建时可用 -PDEFAULT_SERVER_URL=xxx 覆盖，
        // 默认生产域名，不再散落在代码里（避免换环境要改源码重打包）。
        val defaultServerUrl = (project.findProperty("DEFAULT_SERVER_URL") as String?)
            ?: System.getenv("WMS_SERVER_URL")
            ?: "https://gd2026.top"
        buildConfigField("String", "DEFAULT_SERVER_URL", "\"$defaultServerUrl\"")
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
                // AI-MOB-APK-001：未配置 WMS_STORE_FILE 时走 debug 签名（见 buildTypes.release），
                // 不再强制要求签名参数；一旦配置则必须给全，防止打出无法安装/更新的包。
                if (System.getenv("WMS_STORE_FILE") != null) {
                    val pwd = System.getenv("WMS_STORE_PASSWORD")
                    val keyPwd = System.getenv("WMS_KEY_PASSWORD")
                    val alias = System.getenv("WMS_KEY_ALIAS")
                    if (pwd.isNullOrBlank() || keyPwd.isNullOrBlank() || alias.isNullOrBlank()) {
                        throw GradleException(
                            "release 构建缺少签名参数。请设置 WMS_STORE_PASSWORD / " +
                                "WMS_KEY_ALIAS / WMS_KEY_PASSWORD（keystore 与密码绝不上传仓库）。"
                        )
                    }
                }
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // AI-MOB-APK-001：CI 无 keystore（签名材料绝不上传仓库）。GitHub runner
            // 镜像预置的 debug.keystore 跨构建稳定，且与现行 debug 包同签名，
            // release 包可直接覆盖安装；配置 WMS_STORE_FILE 时自动切正式签名。
            signingConfig = if (System.getenv("WMS_STORE_FILE") != null) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
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
    // （保持默认构建无网络依赖；启用后由 downloadSherpaModel 拉模型、downloadSherpaAar 拉 AAR）
    // 2026-08-26 修复：sherpa-onnx 的 Android AAR 从未发布到 Maven Central
    // （com.k2fsa group 不存在，CI run 32930112111 checkDebugAarMetadata 失败），
    // 官方分发渠道是 GitHub Releases 资产，改为本地 AAR 文件依赖，
    // 由 downloadSherpaAar task 下载到 app/libs/。
    if ((project.findProperty("wms.sherpa") as String?)?.toBooleanStrictOrNull() == true) {
        implementation(files("libs/sherpa-onnx-1.13.6.aar"))
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
//   ./gradlew :app:downloadSherpaModel -Pwms.sherpa=true
//
// 模型下载到 app/src/main/assets/sherpa-onnx/stream/（平铺为引擎期望的标准四件套
// tokens.txt / encoder.onnx / decoder.onnx / joiner.onnx），运行时会随 APK 一起打包，
// 首次启动由 SherpaVoiceSttEngine 复制到 filesDir 后使用，
// 在国内 / 无 Google 服务的设备上提供本地离线中文识别。
// 失败时 task 不抛异常，只 warn；运行时由 SherpaVoiceSttEngine.isAvailable 检测
// 缺失并 fallback 到 AndroidVoiceSttEngine，保证 UI 不退化。
//
// 2026-08-26 修复（AI-MOB-VOICE-F01-fix3）：
// - 原默认 URL 的模型名（sherpa-onnx-streaming-zh-en-2023-06-26）在官方 release
//   中不存在（GitHub 返回 Not Found），改为实际存在的
//   sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23（70.6MB，纯中文流式，
//   transducer 结构 encoder/decoder/joiner 三件套，与引擎期望一致）。
// - 原逻辑 untar 直接落 targetDir，但真实模型包有顶层目录且文件名带 epoch/int8
//   后缀（如 encoder-epoch-99-avg-1.int8.onnx），与引擎期望的四件套文件名不符；
//   现解到临时目录后按"前缀匹配、优先 int8"挑选并平铺重命名为标准文件名。
// - 手机端选 int8 量化变体（体积约为 fp32 的 1/4，APK 增量约 15-20MB），
//   无 int8 时回退 fp32。
// -----------------------------------------------------------------------------
// sherpa-onnx Android AAR 下载任务（官方 AAR 只发 GitHub Releases，不在 Maven Central）。
// 用法：./gradlew :app:downloadSherpaAar -Pwms.sherpa=true
// 下载到 app/libs/sherpa-onnx-1.13.6.aar（构建产物，已在 .gitignore 排除）。
tasks.register("downloadSherpaAar") {
    group = "sherpa"
    description = "下载 sherpa-onnx Android AAR 到 app/libs/"
    val aarVersion = "1.13.6"
    val defaultAarUrl =
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/" +
            "v$aarVersion/sherpa-onnx-$aarVersion.aar"
    val aarUrl = (project.findProperty("aarUrl") as String?) ?: defaultAarUrl
    val targetAar = file("libs/sherpa-onnx-$aarVersion.aar")

    doLast {
        if (targetAar.isFile && targetAar.length() > 1024 * 1024) {
            logger.lifecycle("sherpa-onnx AAR already present at $targetAar, skipping")
            return@doLast
        }
        targetAar.parentFile.mkdirs()
        try {
            ant.withGroovyBuilder {
                "get"(
                    "src" to aarUrl,
                    "dest" to targetAar.absolutePath,
                    "verbose" to true,
                    "usetimestamp" to true
                )
            }
            // AAR 是 zip 结构且体积应为 MB 级；GitHub 302/404 时会落到很小的文件，显式拦截
            if (!targetAar.isFile || targetAar.length() <= 1024 * 1024) {
                targetAar.delete()
                throw IllegalStateException("AAR 下载不完整（${targetAar.length()} bytes），疑似 302/404 未跟随")
            }
            logger.lifecycle("sherpa-onnx AAR downloaded to $targetAar (${targetAar.length() / 1024 / 1024}MB)")
        } catch (t: Throwable) {
            logger.warn(
                "downloadSherpaAar 失败：${t.message}。开启 -Pwms.sherpa=true 构建将缺 AAR 依赖。"
            )
        }
    }
}

tasks.register("downloadSherpaModel") {
    group = "sherpa"
    description = "下载 sherpa-onnx 中文流式识别模型到 assets/sherpa-onnx/stream/（平铺标准四件套）"
    val defaultUrl =
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/" +
            "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23.tar.bz2"
    val modelUrl = (project.findProperty("modelUrl") as String?) ?: defaultUrl
    val targetDir = file("src/main/assets/sherpa-onnx/stream")
    val tmpFile = file("build/sherpa-model.tar.bz2")
    val extractDir = file("build/sherpa-model-extract")

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
            if (!tarFile.isFile) {
                throw IllegalStateException("bunzip2 后未找到 $tarFile（下载可能不完整）")
            }
            extractDir.deleteRecursively()
            extractDir.mkdirs()
            ant.withGroovyBuilder {
                "untar"(
                    "src" to tarFile.absolutePath,
                    "dest" to extractDir.absolutePath,
                    "overwrite" to true
                )
            }
            tarFile.delete()
            tmpFile.delete()

            // 模型包结构：<顶层目录>/{tokens.txt, encoder-*.onnx, decoder-*.onnx, joiner-*.onnx, ...}
            // 顶层目录名随模型版本变化，在解出目录中递归定位含 tokens.txt 的那一层。
            val modelRoot = extractDir.walkTopDown()
                .firstOrNull { it.isFile && it.name == "tokens.txt" }
                ?.parentFile
                ?: throw IllegalStateException("解包后未找到 tokens.txt，模型包结构异常")
            // 按前缀挑选变体：优先 int8（手机端体积/速度最优），无 int8 回退首个匹配（fp32）。
            fun pickVariant(prefix: String): File {
                val cands = modelRoot.listFiles()?.filter {
                    it.isFile && it.name.startsWith(prefix) && it.name.endsWith(".onnx")
                } ?: emptyList()
                return cands.firstOrNull { it.name.contains("int8") }
                    ?: cands.firstOrNull()
                    ?: throw IllegalStateException("模型包中未找到 $prefix*.onnx")
            }
            val renameMap = linkedMapOf(
                File(modelRoot, "tokens.txt") to File(targetDir, "tokens.txt"),
                pickVariant("encoder") to File(targetDir, "encoder.onnx"),
                pickVariant("decoder") to File(targetDir, "decoder.onnx"),
                pickVariant("joiner") to File(targetDir, "joiner.onnx"),
            )
            renameMap.forEach { (src, dst) ->
                src.copyTo(dst, overwrite = true)
                logger.lifecycle("  $dst <- ${src.name} (${src.length() / 1024 / 1024}MB)")
            }
            extractDir.deleteRecursively()

            // 落盘后校验四件套齐全（任一缺失视为失败，保证 CI 校验步骤能拦到）
            val missing = required.filter { !File(targetDir, it).isFile }
            if (missing.isNotEmpty()) {
                throw IllegalStateException("模型落盘不完整，缺：$missing")
            }
            logger.lifecycle("sherpa-onnx model downloaded to $targetDir")
        } catch (t: Throwable) {
            logger.warn(
                "downloadSherpaModel 失败：${t.message}。运行时将 fallback 到 AndroidVoiceSttEngine。"
            )
        }
    }
}