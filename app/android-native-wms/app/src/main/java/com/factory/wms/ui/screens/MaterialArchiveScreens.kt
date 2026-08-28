package com.factory.wms.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.compose.AsyncImagePainter
import coil.compose.rememberAsyncImagePainter
import com.factory.wms.data.api.RetrofitClient
import com.factory.wms.data.model.MaterialArchiveDto
import com.factory.wms.data.model.MaterialArchiveImageDto
import com.factory.wms.ui.components.WmsCard
import com.factory.wms.ui.components.WmsEmptyState
import com.factory.wms.ui.components.WmsOutlinedActionButton
import com.factory.wms.ui.components.WmsPillBadge
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.components.WmsSectionHeader
import com.factory.wms.ui.components.WmsTopBar
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.archive.MaterialArchiveViewModel
import kotlinx.coroutines.launch

/** 每个物料最多支持的档案图片数（与后端一致）。 */
private const val MAX_IMAGES = 5

/** 把后端返回的相对 url（如 /static/uploads/...xx.jpg）拼成可加载的绝对地址。 */
private fun resolveImageUrl(url: String?): String {
    if (url.isNullOrBlank()) return ""
    if (url.startsWith("http://") || url.startsWith("https://")) return url
    val base = RetrofitClient.getBaseUrl().trimEnd('/')
    return if (url.startsWith("/")) "$base$url" else "$base/$url"
}

/**
 * 物料档案搜索列表屏：按编码/名称/规格/品牌搜索，点击进入图片管理。
 */
@Composable
fun MaterialArchiveSearchScreen(
    viewModel: MaterialArchiveViewModel,
    onBack: () -> Unit,
    onOpenDetail: (MaterialArchiveDto) -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsTopBar(
                title = "物料档案",
                subtitle = "搜索物料 · 拍照上传档案图片（最多 $MAX_IMAGES 张）",
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // ── 搜索卡：一体化搜索框 + 主色搜索按钮 ──
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
                colors = CardDefaults.cardColors(containerColor = CardBackground)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Spacer(modifier = Modifier.width(8.dp))
                    Icon(
                        Icons.Outlined.Search,
                        contentDescription = null,
                        tint = Primary,
                        modifier = Modifier.size(22.dp)
                    )
                    OutlinedTextField(
                        value = uiState.keyword,
                        onValueChange = { viewModel.onKeywordChange(it) },
                        singleLine = true,
                        placeholder = {
                            Text(
                                "输入编码 / 名称 / 规格 / 品牌",
                                color = OnSurfaceSecondary,
                                fontSize = 14.sp
                            )
                        },
                        trailingIcon = {
                            if (uiState.keyword.isNotBlank()) {
                                IconButton(onClick = { viewModel.onKeywordChange("") }) {
                                    Icon(
                                        Icons.Filled.Close,
                                        "清空",
                                        tint = OnSurfaceVariant,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                            }
                        },
                        modifier = Modifier.weight(1f),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color.Transparent,
                            unfocusedBorderColor = Color.Transparent
                        ),
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                            imeAction = androidx.compose.ui.text.input.ImeAction.Search
                        ),
                        keyboardActions = androidx.compose.foundation.text.KeyboardActions(
                            onSearch = { viewModel.search() }
                        )
                    )
                    FilledIconButton(
                        onClick = { viewModel.search() },
                        enabled = !uiState.isLoading,
                        modifier = Modifier.size(46.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = Primary
                        )
                    ) {
                        if (uiState.isLoading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(
                                Icons.Outlined.Search,
                                "搜索物料",
                                tint = Color.White,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                    }
                }
            }

            // ── 结果统计 ──
            if (uiState.materials.isNotEmpty()) {
                Row(
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "共 ${uiState.materials.size} 个匹配物料",
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    Text(
                        "点击进入档案图片管理",
                        style = MaterialTheme.typography.labelSmall,
                        color = OnSurfaceSecondary
                    )
                }
            }

            // ── 结果列表 ──
            if (uiState.materials.isEmpty() && !uiState.isLoading) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    WmsEmptyState(
                        icon = Icons.Outlined.Inventory2,
                        title = if (uiState.keyword.isBlank()) "输入关键字搜索物料" else "未找到匹配的物料",
                        subtitle = if (uiState.keyword.isBlank()) "支持编码 / 名称 / 规格 / 品牌模糊搜索" else "换个关键字试试",
                        accentColor = Primary
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(uiState.materials, key = { it.id ?: it.code ?: it.hashCode() }) { material ->
                        MaterialArchiveRow(
                            material = material,
                            onClick = { onOpenDetail(material) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MaterialArchiveRow(
    material: MaterialArchiveDto,
    onClick: () -> Unit
) {
    val hasImages = (material.imageCount ?: 0) > 0
    WmsCard(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
        contentPadding = PaddingValues(14.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            // 物料图标
            Box(
                modifier = Modifier
                    .size(52.dp)
                    .clip(RoundedCornerShape(15.dp))
                    .background(PrimaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Outlined.Category,
                    null,
                    tint = Primary,
                    modifier = Modifier.size(27.dp)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        material.code ?: "",
                        fontWeight = FontWeight.Bold,
                        color = Primary,
                        fontSize = 15.sp,
                        modifier = Modifier.weight(1f, fill = false),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    WmsPillBadge(
                        text = "${material.imageCount ?: 0}/$MAX_IMAGES",
                        icon = Icons.Outlined.Photo,
                        activeColor = Primary,
                        active = hasImages
                    )
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    material.name ?: "",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (!material.spec.isNullOrBlank()) {
                    // BUG-2026-08-28-005：长规格（如 ZB-BVR-450/750V-1*25）单行被省略号
                    // 截断看不全，放宽为最多两行折行显示，超出两行才省略兜底。
                    Text(
                        "规格: ${material.spec}",
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Spacer(modifier = Modifier.height(5.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (!material.unit.isNullOrBlank()) {
                        WmsPillBadge(text = material.unit, activeColor = Tertiary, active = true)
                        Spacer(modifier = Modifier.width(6.dp))
                    }
                    if (!material.category.isNullOrBlank()) {
                        WmsPillBadge(text = material.category, activeColor = Secondary, active = true)
                    }
                }
            }
            Icon(
                Icons.Outlined.ChevronRight,
                null,
                tint = OnSurfaceSecondary,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

/**
 * 物料档案图片管理屏：展示物料信息 + 图片网格，拍照/相册上传，删除图片。
 */
@Composable
fun MaterialArchiveDetailScreen(
    material: MaterialArchiveDto,
    viewModel: MaterialArchiveViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()
    // 点击图片放大预览的大图地址，null 表示未在预览
    var previewImageUrl by remember { mutableStateOf<String?>(null) }

    // 进入页面即加载该物料的档案图片
    LaunchedEffect(material.id) {
        material.id?.let { viewModel.loadImages(it) }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    LaunchedEffect(uiState.success) {
        uiState.success?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
            viewModel.clearSuccess()
        }
    }

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            val id = material.id ?: return@let
            coroutineScope.launch {
                viewModel.uploadImage(id, uriToMultipart(it, context, "image"))
            }
        }
    }

    val launchCamera = rememberCameraLauncherWithPermission(
        snackbarHostState = snackbarHostState,
        onImageCaptured = { bitmap ->
            val uri = saveBitmapToCacheAndGetUri(context, bitmap, "matarchive")
            val id = material.id ?: return@rememberCameraLauncherWithPermission
            if (uri != null) {
                coroutineScope.launch {
                    viewModel.uploadImage(id, uriToMultipart(uri, context, "image"))
                }
            }
        }
    )

    val images = uiState.images
    val canUpload = images.size < MAX_IMAGES

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            WmsTopBar(
                title = "物料档案图片",
                subtitle = "${material.code ?: ""} ${material.name ?: ""}".trim(),
                onBack = onBack
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // ── 物料信息卡 ──
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                shape = RoundedCornerShape(18.dp),
                colors = CardDefaults.cardColors(
                    containerColor = PrimaryContainer.copy(alpha = 0.45f)
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            material.code ?: "",
                            fontWeight = FontWeight.Bold,
                            color = Primary,
                            fontSize = 16.sp,
                            modifier = Modifier.weight(1f, fill = false),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        WmsPillBadge(
                            text = "${images.size}/$MAX_IMAGES 张",
                            icon = Icons.Outlined.Photo,
                            activeColor = Primary,
                            active = images.isNotEmpty()
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        material.name ?: "",
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium
                    )
                    if (!material.spec.isNullOrBlank()) {
                        Text(
                            "规格: ${material.spec}",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant
                        )
                    }
                    Text(
                        "${material.unit ?: ""} · ${material.category ?: ""}",
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    WmsPrimaryButton(
                        text = "打印标签",
                        icon = Icons.Outlined.Print,
                        onClick = { material.id?.let { viewModel.printMaterial(it) } },
                        modifier = Modifier.fillMaxWidth(),
                        loading = uiState.printing,
                        enabled = material.id != null
                    )
                }
            }

            // ── 上传操作区 ──
            WmsCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
            ) {
                WmsSectionHeader(
                    title = "上传档案图片",
                    icon = Icons.Outlined.CameraAlt,
                    iconTint = Primary
                )
                if (!canUpload) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "每个物料最多上传 $MAX_IMAGES 张图片，已达上限，请先删除后再上传。",
                        style = MaterialTheme.typography.bodySmall,
                        color = Error
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    WmsPrimaryButton(
                        text = "拍照",
                        icon = Icons.Outlined.CameraAlt,
                        onClick = { launchCamera() },
                        modifier = Modifier.weight(1f),
                        enabled = canUpload && !uiState.uploading
                    )
                    WmsOutlinedActionButton(
                        text = "选择图片",
                        icon = Icons.Outlined.PhotoLibrary,
                        onClick = { imagePicker.launch("image/*") },
                        modifier = Modifier.weight(1f),
                        enabled = canUpload && !uiState.uploading
                    )
                }
                if (uiState.uploading) {
                    Spacer(modifier = Modifier.height(12.dp))
                    LinearProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(4.dp)),
                        color = Primary,
                        trackColor = PrimaryContainer
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        "图片上传中...",
                        style = MaterialTheme.typography.labelSmall,
                        color = OnSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // ── 图片网格 ──
            if (uiState.isLoading && images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }
            } else if (images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    WmsEmptyState(
                        icon = Icons.Outlined.Photo,
                        title = "暂无档案图片",
                        subtitle = "点击上方拍照 / 选择图片上传",
                        accentColor = Primary
                    )
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(3),
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(images, key = { it.id ?: it.hashCode() }) { image ->
                        ArchiveImageCell(
                            image = image,
                            deleting = uiState.deletingId == image.id,
                            onPreview = { previewImageUrl = resolveImageUrl(image.url) },
                            onDelete = {
                                material.id?.let { mid ->
                                    image.id?.let { viewModel.deleteImage(mid, it) }
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    // 点击图片全屏预览大图，支持双指缩放/拖动，点击任意处或返回键关闭
    previewImageUrl?.let { url ->
        Dialog(onDismissRequest = { previewImageUrl = null }) {
            var scale by remember { mutableStateOf(1f) }
            var offset by remember { mutableStateOf(Offset.Zero) }
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black)
                    .clickable { previewImageUrl = null },
                contentAlignment = Alignment.Center
            ) {
                AsyncImage(
                    model = url,
                    contentDescription = "档案图片大图",
                    modifier = Modifier
                        .fillMaxSize()
                        .pointerInput(Unit) {
                            detectTransformGestures { _, pan, zoom, _ ->
                                scale = (scale * zoom).coerceIn(1f, 5f)
                                offset = if (scale > 1f) offset + pan else Offset.Zero
                            }
                        }
                        .graphicsLayer {
                            scaleX = scale
                            scaleY = scale
                            translationX = offset.x
                            translationY = offset.y
                        },
                    contentScale = ContentScale.Fit
                )
            }
        }
    }
}

/** 图片网格单元：正方形缩略图 + 序号角标 + 删除按钮。 */
@Composable
private fun ArchiveImageCell(
    image: MaterialArchiveImageDto,
    deleting: Boolean,
    onPreview: () -> Unit,
    onDelete: () -> Unit
) {
    val imageUrl = resolveImageUrl(image.url)
    val painter = rememberAsyncImagePainter(model = imageUrl)
    val loadFailed = imageUrl.isBlank() || painter.state is AsyncImagePainter.State.Error

    Box(
        modifier = Modifier
            .aspectRatio(1f)
            .clip(RoundedCornerShape(14.dp))
            .background(SurfaceVariant)
    ) {
        if (loadFailed) {
            Column(
                modifier = Modifier.fillMaxSize(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(
                    Icons.Outlined.BrokenImage,
                    "图片加载失败",
                    tint = OnSurfaceSecondary,
                    modifier = Modifier.size(28.dp)
                )
            }
        } else {
            Image(
                painter = painter,
                contentDescription = "档案图片",
                modifier = Modifier
                    .fillMaxSize()
                    .clickable { onPreview() },
                contentScale = ContentScale.Crop
            )
        }

        // 序号角标
        Surface(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(6.dp),
            shape = RoundedCornerShape(8.dp),
            color = Color.Black.copy(alpha = 0.45f)
        ) {
            Text(
                "第 ${(image.sortOrder ?: 0) + 1} 张",
                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                color = Color.White,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium
            )
        }

        // 删除按钮 / 删除中遮罩
        if (deleting) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.45f)),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = Color.White,
                    strokeWidth = 2.dp
                )
            }
        } else {
            Box(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(6.dp)
                    .size(26.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.9f))
                    .clickable { onDelete() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Outlined.Delete,
                    "删除",
                    tint = Error,
                    modifier = Modifier.size(15.dp)
                )
            }
        }
    }
}
