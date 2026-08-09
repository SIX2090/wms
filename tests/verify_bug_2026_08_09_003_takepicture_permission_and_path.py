# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-003 回归测试：Android App"识物盘点"等拍照页点拍照按钮 app 自动退出

根因（两路径叠加）：
  1. app/android-native-wms/.../ui/screens/AiScreens.kt 的
     DocumentOcrScreen / ObjectRecognizeScreen / StocktakeRecognizeScreen
     三个"拍照"按钮直接 `cameraLauncher.launch(null)` 启动
     `ActivityResultContracts.TakePicturePreview()`，但未请求 Android 6+ 运行时
     `CAMERA` 危险权限，未授权时系统相机会立即抛 `SecurityException` 直接闪退。
  2. 拍照回调里 `MediaStore.Images.Media.insertImage(...)` 在 API 29+ 已废弃
     且因 scoped storage 受限可返回 `null`，紧接着 `android.net.Uri.parse(null)`
     抛 `NullPointerException` 第二次闪退（用户拍完照片返回也会崩）。

修复：
  ①AndroidManifest 注册 `androidx.core.content.FileProvider`，authority = `${applicationId}.fileprovider`；
    新增 res/xml/file_paths.xml 仅暴露 cache-path。
  ②AiScreens.kt 末尾新增 `private fun saveBitmapToCacheAndGetUri(context, bitmap, prefix)`：
    把 Bitmap 用 JPEG 90 压缩写入 cacheDir/camera/{prefix}_{ts}.jpg，再走 FileProvider.getUriForFile
    拿到非空 Uri（始终不返回 null 也不会触发 Uri.parse(null) 路径）。
  ③AiScreens.kt 末尾新增 `private @Composable fun rememberCameraLauncherWithPermission`：
    拍照按钮先检查/请求 `Manifest.permission.CAMERA` 运行时权限，授权后才启动 TakePicturePreview；
    未授权时 Snackbar 提示"请授予相机权限后重试"+ "去设置"动作（跳 Settings.ACTION_APPLICATION_DETAILS_SETTINGS）。
  ④三个 `cameraLauncher = rememberLauncherForActivityResult(...)` 替换为调用 helper：
     - DocumentOcrScreen：launchCamera，onImageCaptured 把 Uri 写 selectedImageUri 并 clearOcrResult
     - ObjectRecognizeScreen：launchCamera，onImageCaptured 把 Uri 写 selectedImageUri 并 clearRecognizedMaterial
     - StocktakeRecognizeScreen：launchCamera，onImageCaptured 把 Uri 写 selectedImageUri + countQty=1 + clearRecognizedMaterial
  ⑤三处 `OutlinedButton(onClick = { cameraLauncher.launch(null) }, ...)` 全部改为
     `OutlinedButton(onClick = { launchCamera() }, ...)`。

具体断言：
  T1. AndroidManifest 注册 FileProvider，authority 用 ${applicationId}.fileprovider，
      exported=false, grantUriPermissions=true，meta-data 指向 @xml/file_paths
  T2. res/xml/file_paths.xml 存在且只暴露 <cache-path path="camera/">
  T3. 旧 3 个 `cameraLauncher = rememberLauncherForActivityResult(contract = ActivityResultContracts.TakePicturePreview())`
      块不再直接出现在三个 Screen 主体中（仅允许出现在新 helper 函数体内）
  T4. 旧 `MediaStore.Images.Media.insertImage(...)` + `Uri.parse(path)` 链式调用彻底清零
  T5. 三个 `OutlinedButton(onClick = { cameraLauncher.launch(null) }, ...)` 全部改为
      `OutlinedButton(onClick = { launchCamera() }, ...)`
  T6. `rememberCameraLauncherWithPermission` 私有 Composable 函数存在，使用
      `ActivityResultContracts.RequestPermission()` 请求 `Manifest.permission.CAMERA`
  T7. `saveBitmapToCacheAndGetUri` 私有函数存在，内部用 `FileProvider.getUriForFile(...)`
      暴露 Uri，不再使用 `MediaStore.Images.Media.insertImage`

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_003_takepicture_permission_and_path.py -xvs
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID_DIR = ROOT / "app" / "android-native-wms" / "app" / "src" / "main"
AI_SCREENS_KT = ANDROID_DIR / "java" / "com" / "factory" / "wms" / "ui" / "screens" / "AiScreens.kt"
MANIFEST_XML = ANDROID_DIR / "AndroidManifest.xml"
FILE_PATHS_XML = ANDROID_DIR / "res" / "xml" / "file_paths.xml"


def _src() -> str:
    raw = AI_SCREENS_KT.read_text(encoding="utf-8")
    # 去掉 Kotlin 注释（// 单行、/* ... */ 块），避免历史 BUG 注释文本触发误报。
    # 注意：必须避免匹配字符串里的 `image/*` 之类的文本——用 (?<!\S) 限制 `/*` 前面必须是空白或行首。
    no_block = re.sub(r"(?<!\S)/\*.*?\*/", "", raw, flags=re.DOTALL)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


def _manifest() -> str:
    return MANIFEST_XML.read_text(encoding="utf-8")


def _file_paths() -> str:
    return FILE_PATHS_XML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T1. AndroidManifest 必须注册 FileProvider
# ---------------------------------------------------------------------------
def test_t1_fileprovider_registered_in_manifest():
    """AndroidManifest 必须注册 androidx.core.content.FileProvider，且 authority 用 ${applicationId}.fileprovider"""
    m = _manifest()
    # provider 节点
    assert re.search(
        r'<provider\s+android:name="androidx\.core\.content\.FileProvider"',
        m,
    ), "缺少 FileProvider provider 节点"
    # authority 必须用 ${applicationId}.fileprovider（与代码 FileProvider.getUriForFile 用 context.packageName + ".fileprovider" 对齐）
    assert re.search(
        r'android:authorities="\$\{applicationId\}\.fileprovider"',
        m,
    ), "FileProvider authority 必须用 ${applicationId}.fileprovider"
    # exported=false, grantUriPermissions=true
    assert re.search(
        r'<provider[^>]*android:exported="false"', m, re.DOTALL
    ), "FileProvider 必须 android:exported=false"
    assert re.search(
        r'<provider[^>]*android:grantUriPermissions="true"', m, re.DOTALL
    ), "FileProvider 必须 android:grantUriPermissions=true"
    # meta-data 指向 @xml/file_paths
    assert re.search(
        r'<meta-data\s+android:name="android\.support\.FILE_PROVIDER_PATHS"\s+'
        r'android:resource="@xml/file_paths"',
        m,
    ), "FileProvider meta-data 必须指向 @xml/file_paths"


# ---------------------------------------------------------------------------
# T2. res/xml/file_paths.xml 必须存在且只暴露 cache-path
# ---------------------------------------------------------------------------
def test_t2_file_paths_xml_exposes_cache_only():
    """file_paths.xml 必须存在，且只暴露 cache-path/path=camera/（最小权限原则）"""
    assert FILE_PATHS_XML.exists(), "缺少 res/xml/file_paths.xml"
    body = _file_paths()
    assert "<cache-path" in body, "file_paths.xml 必须包含 <cache-path>"
    assert re.search(r'<cache-path[^>]*path="camera/"', body), (
        "file_paths.xml 必须暴露 <cache-path path='camera/'>"
    )
    # 不应暴露外部存储/根目录等高权限路径
    for forbidden in ("<external-path", "<external-files-path", "<external-cache-path",
                      "<files-path", "<root-path", "<external-cache-path"):
        assert forbidden not in body, (
            f"file_paths.xml 不应暴露 {forbidden}（最小权限原则）"
        )


# ---------------------------------------------------------------------------
# T3. 旧 3 个直接 cameraLauncher = rememberLauncherForActivityResult(...) 块清零
#     （允许新 helper 内部使用）
# ---------------------------------------------------------------------------
def test_t3_three_screen_level_camera_launchers_removed():
    """三个 Screen 函数体内不再直接 rememberLauncherForActivityResult(TakePicturePreview)，
    仅允许出现在新 helper 内部。"""
    src = _src()
    # 三个 Screen 名字
    screen_names = [
        "DocumentOcrScreen",
        "ObjectRecognizeScreen",
        "StocktakeRecognizeScreen",
    ]
    for name in screen_names:
        # 在 fun {name}( ... ) = rememberLauncherForActivityResult( ... TakePicturePreview ) ... 块
        # 用 lazy DOTALL 模式找 Screen 函数体内（紧跟函数定义后）的 TakePicturePreview launcher
        m = re.search(
            rf"fun\s+{name}\s*\([^)]*\)[^{{]*\{{"
            rf"(?P<body>(?:[^{{}}]|\{{[^{{}}]*\}})*?)"
            rf"rememberLauncherForActivityResult\s*\(\s*"
            rf"contract\s*=\s*ActivityResultContracts\.TakePicturePreview\s*\(",
            src,
            re.DOTALL,
        )
        assert m is None, (
            f"{name} 函数体内仍存在 rememberLauncherForActivityResult(TakePicturePreview)，"
            f"必须替换为 launchCamera = rememberCameraLauncherWithPermission(...)"
        )


# ---------------------------------------------------------------------------
# T4. 旧 MediaStore.Images.Media.insertImage(...) + Uri.parse(path) 链式调用清零
# ---------------------------------------------------------------------------
def test_t4_insertimage_and_uri_parse_null_path_removed():
    """旧写法 `MediaStore.Images.Media.insertImage(...)` + `android.net.Uri.parse(path)` 必须清零，
    仅允许在注释里出现以说明历史 bug。"""
    src = _src()
    # 1) `MediaStore.Images.Media.insertImage(...)` 调用必须清零
    #    严格匹配根因代码 `MediaStore.Images.Media.insertImage(`
    assert not re.search(r"MediaStore\.Images\.Media\.insertImage\s*\(", src), (
        "MediaStore.Images.Media.insertImage(...) 仍被调用，"
        "必须替换为 saveBitmapToCacheAndGetUri(...)（写 cacheDir + FileProvider URI）"
    )
    # 2) Uri.parse(path) / Uri.parse(insertImage(...)) 这种把可能为 null 的 String 喂给 Uri.parse 的写法必须清零
    #    注意：helper 里用了 Uri.fromParts("package", ...) 是合法用法
    assert not re.search(r"Uri\.parse\s*\(\s*path\s*\)", src), (
        "Uri.parse(path) 仍存在——这是 BUG 根因，必须改为 FileProvider.getUriForFile"
    )


# ---------------------------------------------------------------------------
# T5. 三个拍照按钮的 onClick 必须改为 launchCamera()
# ---------------------------------------------------------------------------
def test_t5_three_takephoto_buttons_use_launchcamera():
    """3 个拍照 OutlinedButton.onClick 必须改为 launchCamera()，cameraLauncher.launch(null) 清零。"""
    src = _src()
    # 计数：3 个拍照按钮的 onClick = { launchCamera() }
    launch_camera_clicks = re.findall(r"onClick\s*=\s*\{\s*launchCamera\s*\(\s*\)\s*\}", src)
    assert len(launch_camera_clicks) == 3, (
        f"应恰好 3 个拍照按钮的 onClick = {{ launchCamera() }}，"
        f"实际 {len(launch_camera_clicks)} 个"
    )
    # 业务按钮里不应再有 cameraLauncher.launch(null)——仅允许出现在新 helper 内部
    # 业务按钮指的是 OutlinedButton 上下文里出现 cameraLauncher.launch(null)
    business_camera_launch = re.findall(
        r"onClick\s*=\s*\{\s*cameraLauncher\.launch\s*\(\s*null\s*\)\s*\}", src
    )
    assert len(business_camera_launch) == 0, (
        f"业务按钮仍存在 cameraLauncher.launch(null) 共 {len(business_camera_launch)} 处，"
        f"必须改为 launchCamera()"
    )


# ---------------------------------------------------------------------------
# T6. rememberCameraLauncherWithPermission helper 存在并用 RequestPermission
# ---------------------------------------------------------------------------
def test_t6_helper_requests_runtime_camera_permission():
    """rememberCameraLauncherWithPermission 私有 Composable 必须存在，使用
    ActivityResultContracts.RequestPermission() 请求 Manifest.permission.CAMERA。"""
    src = _src()
    # 函数定义
    assert re.search(
        r"@Composable\s+private\s+fun\s+rememberCameraLauncherWithPermission\s*\(",
        src,
    ), "缺少 rememberCameraLauncherWithPermission 私有 Composable helper"
    # 使用 RequestPermission 契约
    assert re.search(
        r"ActivityResultContracts\.RequestPermission\s*\(\s*\)", src
    ), "helper 未使用 ActivityResultContracts.RequestPermission()"
    # 请求 Manifest.permission.CAMERA
    assert re.search(
        r"Manifest\.permission\.CAMERA", src
    ), "helper 未请求 Manifest.permission.CAMERA"
    # ContextCompat.checkSelfPermission 守卫
    assert "ContextCompat.checkSelfPermission" in src, (
        "helper 缺少 ContextCompat.checkSelfPermission 运行时权限检查守卫"
    )
    # 拒绝时 Snackbar + Settings.ACTION_APPLICATION_DETAILS_SETTINGS
    assert "Settings.ACTION_APPLICATION_DETAILS_SETTINGS" in src, (
        "helper 缺少 Settings.ACTION_APPLICATION_DETAILS_SETTINGS 跳转"
    )
    assert "请授予相机权限后重试" in src, (
        "helper 缺少未授权时的中文提示文案"
    )


# ---------------------------------------------------------------------------
# T7. saveBitmapToCacheAndGetUri 函数存在并用 FileProvider.getUriForFile
# ---------------------------------------------------------------------------
def test_t7_save_bitmap_uses_fileprovider():
    """saveBitmapToCacheAndGetUri 必须存在，内部用 FileProvider.getUriForFile 暴露 Uri，缓存写入 cacheDir/camera/。"""
    src = _src()
    assert re.search(
        r"private\s+fun\s+saveBitmapToCacheAndGetUri\s*\(",
        src,
    ), "缺少 saveBitmapToCacheAndGetUri 私有函数"
    assert "FileProvider.getUriForFile" in src, (
        "saveBitmapToCacheAndGetUri 未使用 FileProvider.getUriForFile"
    )
    assert "context.cacheDir" in src, (
        "saveBitmapToCacheAndGetUri 必须写入 context.cacheDir 而非 MediaStore"
    )
    # Uri 拼接：用 packageName + ".fileprovider" 与 manifest authority 对齐
    assert re.search(
        r"\$\{context\.packageName\}\.fileprovider", src
    ), "FileProvider authority 拼接必须用 ${context.packageName}.fileprovider"
    # Bitmap.compress JPEG 90
    assert re.search(
        r"Bitmap\.CompressFormat\.JPEG,\s*90", src
    ), "saveBitmapToCacheAndGetUri 应以 JPEG 90 压缩缓存图片"
    # 异常吞掉返回 null 而非抛——兼容两种 Kotlin 写法：
    #   a) `} catch (...) { ... return null }`
    #   b) `return try { ... } catch (...) { Log.e(...); null }`（catch 块最后表达式 = null）
    catch_block = re.search(
        r"catch\s*\([^)]+\)\s*\{(?P<body>[^}]*)\}", src, re.DOTALL,
    )
    assert catch_block is not None, (
        "saveBitmapToCacheAndGetUri 缺少 catch 块（异常必须被吞掉而非抛）"
    )
    body = catch_block.group("body")
    # 块内最后非空行要么是 `return null`，要么是单独一行的 `null`（Kotlin 隐式 return）
    tail = re.sub(r"\s+", "", body)
    assert tail.endswith("returnnull") or tail.endswith("null") or re.search(
        r"return\s+null", body,
    ) or re.search(r"\bnull\b\s*$", body, re.DOTALL), (
        "saveBitmapToCacheAndGetUri 失败时必须返回 null（return null 或 catch 块最后表达式为 null）"
    )
