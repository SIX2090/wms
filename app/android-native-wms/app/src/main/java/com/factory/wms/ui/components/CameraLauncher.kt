package com.factory.wms.ui.components

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.MediaStore
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.ActivityResultContracts
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
    // 待写入的输出文件：launch 前预建，结果回调里按成功/取消决定回传或删除。
    var pendingCapture by remember { mutableStateOf<Pair<Uri, File>?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        val pending = pendingCapture
        pendingCapture = null
        if (success && pending != null) {
            onImageCaptured(pending.first)
        } else {
            // 取消或拍摄失败：删除预建的空文件，避免缓存目录积累 0 字节垃圾。
            pending?.second?.delete()
        }
    }

    // 预建输出文件并向所有可处理拍照的应用显式授予写权限——TakePicture 契约生成的
    // intent 不附带 grant flag，不授权时部分 OEM 相机写不回 EXTRA_OUTPUT（空文件/失败回调）。
    fun startCapture() {
        val dir = File(context.cacheDir, "camera").apply { mkdirs() }
        val file = File(dir, "cap_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )
        val captureIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        context.packageManager
            .queryIntentActivities(captureIntent, PackageManager.MATCH_DEFAULT_ONLY)
            .forEach { info ->
                context.grantUriPermission(
                    info.activityInfo.packageName,
                    uri,
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
            }
        pendingCapture = uri to file
        cameraLauncher.launch(uri)
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
