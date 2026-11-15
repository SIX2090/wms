package com.factory.wms.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.window.DialogProperties
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.FontFamily
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
import com.factory.wms.ui.components.WmsErrorState
import com.factory.wms.ui.components.WmsListSkeleton
import com.factory.wms.ui.components.WmsOutlinedActionButton
import com.factory.wms.ui.components.WmsPillBadge
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.components.rememberCameraLauncherWithPermission
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

    // BUG-2026-09-14-035：进入物料档案即加载全部物料（空关键字后端返回全量，不再截断前 50）。
    LaunchedEffect(Unit) {
        viewModel.search()
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：此处只剩"带结果搜索失败"的瞬态错误（首屏失败走
            // loadError 全屏错误态），Snackbar 加长避免现场没看清就消失。
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
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

            // ── 结果列表 / 骨架 / 空态 / 错误态 ──
            when {
                // AI-APP-FIX-202：首屏加载（此前是空白屏等结果）→ 骨架列表
                uiState.isLoading && uiState.materials.isEmpty() -> {
                    WmsListSkeleton(modifier = Modifier.weight(1f))
                }

                // AI-APP-FIX-201：首屏加载失败 → 全屏错误态 + 重试，
                // 不再落入下方"暂无物料档案"的误导性空态
                uiState.loadError != null && uiState.materials.isEmpty() -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = Alignment.Center
                    ) {
                        WmsErrorState(
                            title = "加载失败",
                            subtitle = uiState.loadError ?: "请检查网络后重试",
                            onRetry = { viewModel.search() }
                        )
                    }
                }

                uiState.materials.isEmpty() -> {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .weight(1f),
                        contentAlignment = Alignment.Center
                    ) {
                        WmsEmptyState(
                            icon = Icons.Outlined.Inventory2,
                            // BUG-2026-09-14-035：进入即自动加载全部，空关键字仍为空 = 档案尚无物料
                            title = if (uiState.keyword.isBlank()) "暂无物料档案" else "未找到匹配的物料",
                            subtitle = if (uiState.keyword.isBlank()) "可先在电脑端新建物料，或按编码/名称/规格/品牌搜索" else "换个关键字试试",
                            accentColor = Primary
                        )
                    }
                }

                else -> {
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
}

@Composable
internal fun MaterialArchiveRow(
    material: MaterialArchiveDto,
    onClick: () -> Unit
) {
    WmsCard(modifier = Modifier.fillMaxWidth(), onClick = onClick, contentPadding = PaddingValues(16.dp)) {
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(material.code?.takeIf { it.isNotBlank() } ?: "编码未获取",
                    modifier = Modifier.weight(1f), fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold,
                    color = Primary.readableOn(CardBackground), softWrap = true)
                Icon(Icons.Outlined.ChevronRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(24.dp))
            }
            Text(material.name?.takeIf { it.isNotBlank() } ?: "名称未获取",
                style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(material.spec?.takeIf { it.isNotBlank() }?.let { "规格：$it" } ?: "规格未获取",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                softWrap = true)
            Text("单位：${material.unit?.takeIf { it.isNotBlank() } ?: "未获取"} · 分类：${material.category?.takeIf { it.isNotBlank() } ?: "未获取"}",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                softWrap = true)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Photo, null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text(material.imageCount?.let { "图片 $it/$MAX_IMAGES" } ?: "图片数量未获取",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
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
    var previewImageIndex by remember { mutableIntStateOf(0) }
    var previewImageTotal by remember { mutableIntStateOf(0) }

    // 进入页面即加载该物料的档案图片
    LaunchedEffect(material.id) {
        material.id?.let { viewModel.loadImages(it) }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            // AI-APP-FIX-201：上传/删除/打印等瞬态错误，Snackbar 加长
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Long)
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

    // AI-APP-FIX-101：随共享拍照入口一并迁移——相机直接回传全尺寸照片 Uri，
    // 档案图片同样受益（大图预览更清晰），不再经过 Bitmap 缩略图 + 二次落盘。
    val launchCamera = rememberCameraLauncherWithPermission(
        snackbarHostState = snackbarHostState,
        onImageCaptured = { uri ->
            val id = material.id ?: return@rememberCameraLauncherWithPermission
            coroutineScope.launch {
                viewModel.uploadImage(id, uriToMultipart(uri, context, "image"))
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
                .verticalScroll(rememberScrollState())
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
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.weight(1f),
                            softWrap = true
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
                    WmsOutlinedActionButton(
                        text = if (uiState.printing) "打印中…" else "打印标签",
                        icon = Icons.Outlined.Print,
                        onClick = { material.id?.let { viewModel.printMaterial(it) } },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = material.id != null && !uiState.printing
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
                        text = "拍照上传",
                        icon = Icons.Outlined.CameraAlt,
                        onClick = { launchCamera() },
                        modifier = Modifier.weight(1f),
                        enabled = canUpload && !uiState.uploading
                    )
                    WmsOutlinedActionButton(
                        text = "相册上传",
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

            // ── 图片网格 / 加载 / 空态 / 错误态 ──
            Text(
                when {
                    uiState.isLoading && images.isEmpty() -> "物料图片 · 加载中"
                    uiState.imagesError != null && images.isEmpty() -> "物料图片 · 未获取"
                    else -> "物料图片 ${images.size}/$MAX_IMAGES"
                },
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (uiState.isLoading && images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 160.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = Primary)
                }
            } else if (uiState.imagesError != null && images.isEmpty()) {
                // AI-APP-FIX-201：图片首载失败 → 错误态 + 重试，
                // 不再伪装成"暂无档案图片"（用户会以为图丢了）
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 160.dp),
                    contentAlignment = Alignment.Center
                ) {
                    WmsErrorState(
                        title = "图片加载失败",
                        subtitle = uiState.imagesError ?: "请检查网络后重试",
                        onRetry = { material.id?.let { viewModel.loadImages(it) } }
                    )
                }
            } else if (images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 160.dp),
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
                Column(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    val cellCount = images.size + if (canUpload) 1 else 0
                    (0 until cellCount).chunked(3).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            row.forEach { index ->
                                if (index < images.size) {
                                    val image = images[index]
                                    Box(Modifier.weight(1f)) {
                                        ArchiveImageCell(
                                            image = image,
                                            displayIndex = index + 1,
                                            deleting = uiState.deletingId == image.id,
                                            onPreview = {
                                                previewImageIndex = index + 1
                                                previewImageTotal = images.size
                                                previewImageUrl = resolveImageUrl(image.url)
                                            },
                                            onDelete = {
                                                material.id?.let { mid -> image.id?.let { viewModel.deleteImage(mid, it) } }
                                            }
                                        )
                                    }
                                } else {
                                    Box(
                                        modifier = Modifier.weight(1f).aspectRatio(1f)
                                            .clip(RoundedCornerShape(14.dp))
                                            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
                                            .clickable(enabled = !uiState.uploading) { imagePicker.launch("image/*") },
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("添加图片", style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurface, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                                    }
                                }
                            }
                            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                        }
                    }
                }
            }
        }
    }

    // 点击图片全屏预览大图，支持双指缩放/拖动，点击任意处或返回键关闭
    previewImageUrl?.let { url ->
        Dialog(onDismissRequest = { previewImageUrl = null }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
            var scale by remember { mutableStateOf(1f) }
            var offset by remember { mutableStateOf(Offset.Zero) }
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black),
                contentAlignment = Alignment.Center
            ) {
                AsyncImage(
                    model = url,
                    contentDescription = "档案图片大图",
                    modifier = Modifier
                        .fillMaxSize()
                        .pointerInput(Unit) {
                            detectTapGestures(
                                onTap = { previewImageUrl = null },
                                onDoubleTap = { scale = 1f; offset = Offset.Zero }
                            )
                        }
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
                IconButton(onClick = { previewImageUrl = null }, modifier = Modifier.align(Alignment.TopEnd).size(48.dp)) {
                    Icon(Icons.Filled.Close, "关闭预览", tint = Color.White)
                }
                Text("$previewImageIndex/$previewImageTotal", color = Color.White,
                    modifier = Modifier.align(Alignment.TopCenter).padding(16.dp), style = MaterialTheme.typography.bodyMedium)
                Text("双指缩放 · 拖动 · 双击复位", color = Color.White,
                    modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

/** 图片网格单元：正方形缩略图 + 序号角标 + 删除按钮。 */
@Composable
private fun ArchiveImageCell(
    image: MaterialArchiveImageDto,
    displayIndex: Int,
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
                "$displayIndex",
                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                color = Color.White,
                fontSize = 14.sp,
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
                    .size(48.dp)
                    .clickable(enabled = image.id != null) { onDelete() },
                contentAlignment = Alignment.Center
            ) {
                Box(Modifier.size(26.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.9f)),
                    contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.Delete, "删除", tint = Error, modifier = Modifier.size(15.dp))
                }
            }
        }
    }
}
