package com.factory.wms.ui.components

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.factory.wms.ui.theme.Background
import com.factory.wms.ui.theme.CardBackground

/**
 * AI 拍照识别三页（识别单据/识物/识物盘点）的公共采集脚手架（AI-APP-FIX-405）。
 *
 * 收敛三页各自重复的约 200 行：图片选中状态、拍照/相册双通道、错误 Snackbar、
 * 渐变头部、图片预览卡（含右上角清除）、虚线空态卡、拍照/选择图片按钮对。
 * 页面只提供头部/空态文案与结果区 content。
 *
 * @param error 页面 ViewModel 的瞬态错误；非空即 Snackbar 并回调 [onClearError]
 * @param onImageChanged 图片变化（相册选中/拍照成功/点清除）后的统一回调
 *   （清识别结果、重置数量等）
 * @param content 页面特有内容（识别按钮 + 结果区），参数为当前图片 Uri 与
 *   脚手架共享的 SnackbarHostState（校验提示必须用同一个 host，否则不显示）
 */
@Composable
fun AiCaptureScaffold(
    title: String,
    subtitle: String,
    accent: Color,
    onBack: () -> Unit,
    error: String?,
    onClearError: () -> Unit,
    emptyIcon: ImageVector,
    emptyTitle: String,
    emptySubtitle: String,
    imageContentDescription: String,
    onImageChanged: () -> Unit,
    content: @Composable ColumnScope.(imageUri: Uri?, snackbarHostState: SnackbarHostState) -> Unit
) {
    var selectedImageUri by remember { mutableStateOf<Uri?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            selectedImageUri = it
            onImageChanged()
        }
    }

    // AI-APP-FIX-101：相机直接回传全尺寸照片 Uri（TakePicture 预建文件），
    // 不再经过 Bitmap 缩略图 + 二次落盘。
    val launchCamera = rememberCameraLauncherWithPermission(
        snackbarHostState = snackbarHostState,
        onImageCaptured = { uri ->
            selectedImageUri = uri
            onImageChanged()
        }
    )

    LaunchedEffect(error) {
        error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            onClearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsGradientHeader(
                title = title,
                subtitle = subtitle,
                accent = accent,
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            if (selectedImageUri != null) {
                // 图片预览卡（右上角圆形清除按钮）
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Box(modifier = Modifier.fillMaxWidth()) {
                        AsyncImage(
                            model = selectedImageUri,
                            contentDescription = imageContentDescription,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(240.dp)
                                .clip(RoundedCornerShape(20.dp)),
                            contentScale = ContentScale.Fit
                        )
                        IconButton(
                            onClick = {
                                selectedImageUri = null
                                onImageChanged()
                            },
                            modifier = Modifier
                                .align(Alignment.TopEnd)
                                .padding(8.dp)
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(Color.Black.copy(alpha = 0.5f))
                        ) {
                            Icon(
                                Icons.Filled.Close,
                                "清除",
                                tint = Color.White,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))
            } else {
                // 虚线空态卡（AI-APP-FIX-405：WmsEmptyState dashedBorder）
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    WmsEmptyState(
                        icon = emptyIcon,
                        title = emptyTitle,
                        subtitle = emptySubtitle,
                        accentColor = accent,
                        dashedBorder = true,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(8.dp)
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                ImageSourcePicker(
                    accent = accent,
                    onCamera = { launchCamera() },
                    onPick = { imagePicker.launch("image/*") }
                )
            }

            content(selectedImageUri, snackbarHostState)
        }
    }
}

/** 拍照 / 选择图片 双通道按钮对（AI-APP-FIX-405，AI 采集页空态下使用）。 */
@Composable
fun ImageSourcePicker(
    accent: Color,
    onCamera: () -> Unit,
    onPick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        WmsOutlinedActionButton(
            text = "拍照",
            onClick = onCamera,
            modifier = Modifier.weight(1f),
            icon = Icons.Outlined.CameraAlt,
            color = accent
        )
        WmsOutlinedActionButton(
            text = "选择图片",
            onClick = onPick,
            modifier = Modifier.weight(1f),
            icon = Icons.Outlined.PhotoLibrary,
            color = accent
        )
    }
}
