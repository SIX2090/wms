package com.factory.wms.ui.components

import android.Manifest
import android.content.Intent
import android.content.ClipData
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import kotlinx.coroutines.launch
import java.io.File

/**
 * 拍照入口（含权限申请与全尺寸回传，AI-APP-FIX-101）。
 *
 * AI-APP-FIX-405：从 AiScreens.kt 迁至 components 包——AiCaptureScaffold 与
 * 物料档案详情页共用。原 internal 可见性不变（同模块内可见）。
 *
 * 行为：相机直接回传全尺寸照片 Uri（TakePicture + FileProvider 预建文件），
 * 不经过 Bitmap 缩略图 + 二次落盘；取消/失败时删除预建的 0 字节文件；
 * 权限被拒时 Snackbar 给出去系统设置的入口。
 */
@Composable
internal fun rememberCameraLauncherWithPermission(
    snackbarHostState: SnackbarHostState,
    onImageCaptured: (Uri) -> Unit
): () -> Unit {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    // 外部相机打开期间 Android 可能重建页面，保存输出文件名供结果回调恢复。
    var pendingCapture by rememberSaveable { mutableStateOf<String?>(null) }
    val cameraDir = File(context.cacheDir, "camera")

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = object : ActivityResultContracts.TakePicture() {
            override fun createIntent(context: Context, input: Uri): Intent =
                super.createIntent(context, input).apply {
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                    clipData = ClipData.newRawUri("camera output", input)
                }
        }
    ) { success ->
        val file = pendingCapture?.let { File(cameraDir, it) }
        pendingCapture = null
        if (file != null) {
            if (success) {
                onImageCaptured(FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file))
            } else {
                file.delete()
            }
        }
    }

    fun startCapture() {
        if (pendingCapture != null) return
        cameraDir.mkdirs()
        val file = File.createTempFile("cap_", ".jpg", cameraDir)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        pendingCapture = file.name
        try {
            cameraLauncher.launch(uri)
        } catch (_: android.content.ActivityNotFoundException) {
            pendingCapture = null
            file.delete()
            coroutineScope.launch { snackbarHostState.showSnackbar("找不到可用的相机应用") }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startCapture()
        } else {
            coroutineScope.launch {
                val result = snackbarHostState.showSnackbar(
                    message = "请授予相机权限后重试",
                    actionLabel = "去设置",
                    duration = SnackbarDuration.Long
                )
                if (result == SnackbarResult.ActionPerformed) {
                    val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = Uri.fromParts("package", context.packageName, null)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    context.startActivity(intent)
                }
            }
        }
    }

    return {
        if (ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            startCapture()
        } else {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }
}
