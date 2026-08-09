# WMS 手机端 sherpa-onnx 离线语音识别集成文档

> 适用版本：`app/android-native-wms` 当前 `main` 分支
> 适用模块：`com.factory.wms.ui.viewmodel.voice.*`（`VoiceSttEngine` / `AndroidVoiceSttEngine` / `SherpaVoiceSttEngine` / `SherpaRuntime` / `VoiceCommandViewModel` / `VoiceSttEngineRegistry`）
> 状态：默认构建未启用；通过 `-Pwms.sherpa=true` + `downloadSherpaModel` 拉模型启用；缺模型时自动 fallback 到 Android 系统识别。

---

## 1. 背景与目标

### 1.1 现状（修前）

`VoiceCommandViewModel` 直接调用 `android.speech.SpeechRecognizer`：

- 国内 ROM（MIUI / EMUI / ColorOS / OriginOS 等）多数未装 Google 服务，`SpeechRecognizer.createSpeechRecognizer` 返回的对象**静默挂起**：不回调 `onPartial` / `onResults` / `onError`，UI 永远停在"正在聆听"。
- 已通过 `BUG-2026-08-09-003` 引入 8 秒兜底超时（`VOICE_LISTEN_TIMEOUT_MS = 8_000L`），但识别本身在多数国内设备上仍失败。
- 网络要求：`SpeechRecognizer` 走 Google 云端，国内网络下既慢又经常超时（`ERROR_NETWORK` / `ERROR_NETWORK_TIMEOUT`）。

### 1.2 目标

- 引入**完全离线**的中文语音识别（无网络、无 Google 服务依赖）。
- 引擎**可选**：通过 gradle 属性开关，**默认不引入 AAR**，保留现有构建产物零侵入。
- **无缝 fallback**：sherpa 不可用（未下载模型 / 设备 ABI 不支持）时自动回退到系统识别，UI 不退化。
- **反射调用**：编译期不 `import com.k2fsa.sherpa.*`，缺 AAR 时也能正常 `assembleDebug`，CI 不会因 sherpa 编译失败而挂。

### 1.3 选型

| 候选 | 优点 | 缺点 | 是否选用 |
|---|---|---|---|
| **sherpa-onnx** | 免费 / 国内直连 GitHub / 中文流式识别 / AAR 含 `.so` / 活跃维护 | 首次需下载 ~300MB 模型 | **是** |
| 阿里云 / 腾讯云 ASR | 中文识别率高 | 按量计费 / 国内必须联网 / 引入密钥 | 否 |
| Vosk | 离线轻量 | 中文模型小、识别率低 | 否 |
| Whisper.cpp | 准确率高 | 模型大（>500MB）、不支持流式 | 否 |
| 继续用 SpeechRecognizer | 零成本 | 国内无 Google 服务 | 否（保留为 fallback） |

---

## 2. 架构

### 2.1 类图

```
                     ┌───────────────────────────┐
                     │   VoiceSttEngine (iface)  │
                     │  isAvailable / start /    │
                     │  stop / destroy / setListener
                     └──────────┬────────────────┘
                                │ implements
            ┌───────────────────┴────────────────────┐
            │                                        │
┌───────────────────────────┐         ┌─────────────────────────────┐
│  AndroidVoiceSttEngine    │         │  SherpaVoiceSttEngine       │
│  (基于 SpeechRecognizer)  │         │  (基于 AudioRecord + sherpa) │
│  - 系统识别封装            │         │  - AudioRecord 录音          │
│  - 错误码 -> SttError      │         │  - 反射调用 sherpa-onnx      │
│  - 国内 fallback 路径       │         │  - 流式 partial 推送          │
└───────────────────────────┘         └──────────────┬──────────────┘
                                                       │ delegates feed/poll
                                                       ▼
                                          ┌──────────────────────────┐
                                          │  SherpaRuntime (反射)     │
                                          │  - Class.forName          │
                                          │  - Method.invoke          │
                                          │  - feed / pollPartial /   │
                                          │    pollFinal / destroy    │
                                          └──────────────────────────┘

                 ┌────────────────────────────────────┐
                 │  VoiceSttEngineRegistry (单例)      │
                 │  defaultSelector:                   │
                 │    sherpa = SherpaVoiceSttEngine()  │
                 │    if sherpa.isAvailable()          │
                 │        return sherpa                │
                 │    else return AndroidVoiceSttEngine│
                 │  setSelector(selector): 单测/设置用  │
                 └────────────────────────────────────┘
```

### 2.2 音频管线

```
AudioRecord(16kHz mono PCM16, VOICE_RECOGNITION source)
   │  read(buf, FRAME_SAMPLES=1600)  // 100ms / 帧
   ▼
ShortArray(1600)
   │  for each sample: FloatArray[i] = short[i] / 32768f
   ▼
FloatArray(-1.0..1.0, sampleRate=16000)
   │  runtime.feed(samples, sampleRate)
   ▼
sherpa-onnx OnlineStream.acceptWaveform
   │  runtime.pollPartial() -> String?
   ▼
listener?.onPartial(text)   // 推给 ViewModel，更新 UI
```

### 2.3 生命周期

| 阶段 | 调用方 | 引擎行为 | 错误兜底 |
|---|---|---|---|
| `isAvailable()` | Registry 选引擎时 | 校验模型文件 + 反射探测 classpath | 返回 false → fallback |
| `start()` | ViewModel 点击麦克风 | 反射创建 runtime + 启 AudioRecord | try-catch Throwable → `EngineUnavailable` |
| `stop()` | 用户取消 / UI 关闭 | 停 AudioRecord + `pollFinal` 推 onResult | 异常仅 warn |
| `destroy()` | ViewModel.onCleared | stop + release + 置空 listener | 多次调用安全 |

---

## 3. 启用与构建

### 3.1 默认构建（不引入 sherpa AAR）

```bash
cd /workspace/app/android-native-wms
./gradlew :app:assembleDebug    # 不带 -Pwms.sherpa → 不拉 AAR
```

行为：

- `SherpaVoiceSttEngine.isAvailable()` 返回 false（`ClassNotFoundException`）
- `VoiceSttEngineRegistry` 自动 fallback 到 `AndroidVoiceSttEngine`
- UI 行为与原版完全一致
- APK 体积不变

### 3.2 启用本地离线识别

```bash
# 1) 开启依赖（仅本次构建生效）
./gradlew :app:assembleDebug -Pwms.sherpa=true

# 2) 下载中文流式模型到 src/main/assets/sherpa-onnx/stream/
./gradlew :app:downloadSherpaModel -Pwms.sherpa=true
# 或指定其他模型：
./gradlew :app:downloadSherpaModel \
  -Pwms.sherpa=true \
  -PmodelUrl=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zh-en-2023-06-26.tar.bz2

# 3) 重新构建（让 assets/ 被打进 APK）
./gradlew :app:assembleDebug -Pwms.sherpa=true
```

### 3.3 buildConfigField 暴露

`app/build.gradle.kts` 写入：

```kotlin
buildConfigField("boolean", "SHERPA_ENABLED", enableSherpa.toString())
buildConfigField(
    "String",
    "SHERPA_MODEL_DIR",
    "\"${System.getenv("WMS_SHERPA_MODEL_DIR") ?: "sherpa-onnx/stream"}\""
)
```

可通过 `WMS_SHERPA_MODEL_DIR` 环境变量覆盖默认 `sherpa-onnx/stream`，便于自定义模型目录。

### 3.4 运行时模型目录

`SherpaVoiceSttEngine.defaultModelDir()`：

```kotlin
File(appContext.filesDir, "sherpa-onnx/stream")
```

要求目录存在以下 4 个文件：

| 文件 | 来源 | 必需 |
|---|---|---|
| `tokens.txt` | `downloadSherpaModel` 解压产物 | 是 |
| `encoder.onnx` | 同上 | 是 |
| `decoder.onnx` | 同上 | 是 |
| `joiner.onnx` | 同上 | 是 |

**首次部署到设备**后建议把模型从 `assets/sherpa-onnx/stream/` 复制到 `filesDir/sherpa-onnx/stream/`（`SherpaVoiceSttEngine` 实际加载路径是 `filesDir`）。当前实现仅以 `filesDir` 为准，assets 路径未启用——如需"assets → filesDir 一次性拷贝"，可在后续 PR 加 `assets.open(...).copyTo(filesDir/...)` 引导逻辑。

---

## 4. fallback 行为

### 4.1 引擎选择时序

```
VoiceSttEngineRegistry.create(context)
  └─ defaultSelector(context)
       ├─ sherpa = SherpaVoiceSttEngine(context)
       └─ if sherpa.isAvailable() return sherpa   // 4 个模型齐 + 反射探测通过
           else return AndroidVoiceSttEngine(context)  // fallback
```

### 4.2 fallback 触发条件

| 场景 | 行为 |
|---|---|
| `-Pwms.sherpa=true` 未传 | `enableSherpa=false` → AAR 不引入 → `probeClassloader` 返 false → fallback |
| 模型文件不全（任意一个缺失） | `isAvailable` 返 false → fallback |
| `Class.forName` 抛 `ClassNotFoundException` | `probeClassloader` 返 false → fallback |
| 反射调用时 `JNI .so` 加载失败 | `SherpaRuntime.create` 返 null → `start` 推 `EngineUnavailable` → UI 显示"当前设备不支持语音识别" |

### 4.3 强制走系统识别（单测 / 用户偏好）

```kotlin
// 测试场景
VoiceSttEngineRegistry.setSelector { ctx -> AndroidVoiceSttEngine(ctx) }

// 还原
VoiceSttEngineRegistry.setSelector { ctx -> defaultSelector(ctx) }
```

---

## 5. 测试

### 5.1 静态断言（已写）

| 测试文件 | 覆盖范围 | 用例数 |
|---|---|---|
| `tests/verify_sherpa_voice_stt_engine.py` | `SherpaVoiceSttEngine` 接口实现 / `SherpaRuntime` 反射 / `VoiceSttEngineRegistry` 选择器 | 13 |
| `tests/verify_sherpa_build_config.py` | `buildConfigField` / AAR 开关 / `downloadSherpaModel` task / 失败兜底 | 12 |
| `tests/verify_voice_stt_engine_abstract.py` | `VoiceSttEngine` 抽象 / `SttError` 12 枚举 / `AndroidVoiceSttEngine` / ViewModel 工厂注入 | 14 |
| `tests/verify_sherpa_audio_record_integration.py` | AudioRecord 参数 / 帧大小 / PCM 转 Float / capture 线程 / stop release | 18 |

### 5.2 运行

```bash
cd /workspace
python -m pytest tests/verify_sherpa_*.py tests/verify_voice_stt_engine_abstract.py -xvs --noconftest
```

### 5.3 真机 / 模拟器验证

- 设备：Android 6.0+（`minSdk=26`）、任意 ABI
- 步骤：
  1. 安装带 sherpa 启用的 debug APK
  2. 登录后点悬浮麦克风授权
  3. 说出指令（如"入库"/"出库"/"查库存"）
  4. 观察 partial 实时更新 + 最终结果
- 期望：
  - 无网络：仍可识别（完全离线）
  - 无 Google 服务：仍可识别
  - 8 秒未说话：UI 提示"识别超时，请重试"（兜底超时仍生效）

---

## 6. 已知限制与后续工作

| 限制 | 影响 | 后续 |
|---|---|---|
| 模型目录仅 `filesDir` | 需手动拷贝 assets → filesDir | 增加一次性拷贝引导（首次 `start` 时 copy） |
| 无 VAD 静音检测 | 长按说话需手动结束 | 接 `EndpointRule` 或前端 VAD |
| 不支持热词 / 行业术语 | 物料名识别率低 | 后续接 `hotwords.txt` 注入 |
| 未在 CI 跑端到端识别 | 编译通过 ≠ 识别成功 | 接入 Android instrumentation test + 真实音频 |
| 未做 ProGuard 规则 | release 混淆可能破坏反射 | 在 `proguard-rules.pro` 加 `-keep class com.k2fsa.sherpa.** { *; }` |
| 无方言切换 | 仅支持普通话 zh-CN | 暴露 `SttConfig.language` 给设置页 |

---

## 7. 文件清单

| 路径 | 说明 |
|---|---|
| `app/src/main/java/com/factory/wms/ui/viewmodel/voice/VoiceSttEngine.kt` | 抽象接口 / `SttError` 12 枚举 / `SttConfig` / `VoiceSttListener` |
| `app/src/main/java/com/factory/wms/ui/viewmodel/voice/AndroidVoiceSttEngine.kt` | 系统识别封装（fallback 路径） |
| `app/src/main/java/com/factory/wms/ui/viewmodel/voice/SherpaVoiceSttEngine.kt` | sherpa 引擎实现 + AudioRecord 管线 |
| `app/src/main/java/com/factory/wms/ui/viewmodel/voice/SherpaRuntime.kt` | 反射 wrapper（`feed` / `pollPartial` / `pollFinal` / `destroy`） |
| `app/src/main/java/com/factory/wms/ui/viewmodel/voice/VoiceCommandViewModel.kt` | ViewModel + 8 秒超时 + `VoiceSttEngineRegistry` |
| `app/build.gradle.kts` | `buildConfigField` + AAR 条件依赖 + `downloadSherpaModel` task |
| `app/src/main/AndroidManifest.xml` | `RECORD_AUDIO` 权限（已存在） |
| `tests/verify_sherpa_*.py` | 静态断言 43 用例 |
| `tests/verify_voice_stt_engine_abstract.py` | 抽象层断言 14 用例 |

---

## 8. 引用

- sherpa-onnx 官方仓库：https://github.com/k2-fsa/sherpa-onnx
- 中文流式模型：https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models
- 1.12.13 AAR 坐标：`com.k2fsa.sherpaonnx:sherpa-onnx:1.12.13`（mavenCentral）
- Android `AudioRecord` API：https://developer.android.com/reference/android/media/AudioRecord
- 关联 BUG：`BUG-2026-08-09-003`（语音功能卡在"正在聆听"——已加 8 秒兜底）
- 关联任务：`AI-MOB-VOICE-F01`（[WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md)）
