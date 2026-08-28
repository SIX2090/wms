package com.factory.wms.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
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
@OptIn(ExperimentalMaterial3Api::class)
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
            TopAppBar(
                title = {
                    Column {
                        Text("物料档案", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "搜索物料 · 拍照上传档案图片（最多 $MAX_IMAGES 张）",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Filled.ArrowBack,
                            "返回",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // 搜索框
            OutlinedTextField(
                value = uiState.keyword,
                onValueChange = { viewModel.onKeywordChange(it) },
                singleLine = true,
                placeholder = { Text("输入编码 / 名称 / 规格 / 品牌") },
                leadingIcon = { Icon(Icons.Outlined.Search, null, tint = Primary) },
                trailingIcon = {
                    if (uiState.keyword.isNotBlank()) {
                        IconButton(onClick = { viewModel.onKeywordChange("") }) {
                            Icon(Icons.Filled.Close, "清空", tint = OnSurfaceVariant)
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(16.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    focusedLabelColor = Primary
                ),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
                    imeAction = androidx.compose.ui.text.input.ImeAction.Search
                ),
                keyboardActions = androidx.compose.foundation.text.KeyboardActions(
                    onSearch = { viewModel.search() }
                )
            )

            // 搜索按钮
            Button(
                onClick = { viewModel.search() },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .height(48.dp),
                enabled = !uiState.isLoading,
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = Color.White,
                        strokeWidth = 2.dp
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("搜索中...", fontSize = 15.sp)
                } else {
                    Icon(Icons.Outlined.Search, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("搜索物料", fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 结果列表
            if (uiState.materials.isEmpty() && !uiState.isLoading) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Outlined.Inventory2,
                            null,
                            modifier = Modifier.size(56.dp),
                            tint = OnSurfaceVariant.copy(alpha = 0.4f)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            if (uiState.keyword.isBlank()) "输入关键字搜索物料" else "未找到匹配的物料",
                            style = MaterialTheme.typography.bodyMedium,
                            color = OnSurfaceVariant
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
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
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 物料图标
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(PrimaryContainer),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Outlined.Category,
                    null,
                    tint = Primary,
                    modifier = Modifier.size(26.dp)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    material.code ?: "",
                    fontWeight = FontWeight.Bold,
                    color = Primary,
                    fontSize = 15.sp
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    material.name ?: "",
                    style = MaterialTheme.typography.bodyMedium,
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
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.padding(top = 4.dp)
                ) {
                    Text(
                        "${material.unit ?: ""} · ${material.category ?: ""}",
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant
                    )
                }
            }
            Spacer(modifier = Modifier.width(8.dp))
            // 图片数量角标
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = if ((material.imageCount ?: 0) > 0) PrimaryContainer else SurfaceVariant
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Outlined.Photo,
                        null,
                        tint = if ((material.imageCount ?: 0) > 0) Primary else OnSurfaceVariant,
                        modifier = Modifier.size(14.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        "${material.imageCount ?: 0}/$MAX_IMAGES",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = if ((material.imageCount ?: 0) > 0) Primary else OnSurfaceVariant
                    )
                }
            }
            Icon(
                Icons.Outlined.ChevronRight,
                null,
                tint = OnSurfaceVariant,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

/**
 * 物料档案图片管理屏：展示物料信息 + 图片缩略图，拍照/相册上传，删除图片。
 */
@OptIn(ExperimentalMaterial3Api::class)
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
            TopAppBar(
                title = {
                    Column {
                        Text("物料档案图片", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "${material.code ?: ""} ${material.name ?: ""}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Filled.ArrowBack,
                            "返回",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // 物料信息卡
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = PrimaryContainer.copy(alpha = 0.5f)
                ),
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            material.code ?: "",
                            fontWeight = FontWeight.Bold,
                            color = Primary,
                            fontSize = 16.sp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = if (images.size > 0) PrimaryContainer else SurfaceVariant
                        ) {
                            Text(
                                "${images.size}/$MAX_IMAGES 张",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 3.dp),
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (images.size > 0) Primary else OnSurfaceVariant
                            )
                        }
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
                    Button(
                        onClick = {
                            material.id?.let { viewModel.printMaterial(it) }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(44.dp),
                        enabled = material.id != null && !uiState.printing,
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Primary)
                    ) {
                        if (uiState.printing) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(Icons.Outlined.Print, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("打印标签", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        }
                    }
                }
            }

            // 上传操作区
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = CardBackground),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Outlined.CameraAlt, null, tint = Primary, modifier = Modifier.size(20.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "上传档案图片",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.weight(1f))
                        if (uiState.uploading) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        }
                    }
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
                        Button(
                            onClick = { launchCamera() },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            enabled = canUpload && !uiState.uploading,
                            shape = RoundedCornerShape(14.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = Primary)
                        ) {
                            Icon(Icons.Outlined.CameraAlt, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("拍照", fontWeight = FontWeight.Medium)
                        }
                        OutlinedButton(
                            onClick = { imagePicker.launch("image/*") },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            enabled = canUpload && !uiState.uploading,
                            shape = RoundedCornerShape(14.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary),
                            border = ButtonDefaults.outlinedButtonBorder.copy(
                                brush = androidx.compose.ui.graphics.SolidColor(Primary.copy(alpha = 0.3f))
                            )
                        ) {
                            Icon(Icons.Outlined.PhotoLibrary, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("选择图片", fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // 图片列表
            if (uiState.isLoading && images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator()
                }
            } else if (images.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            Icons.Outlined.Photo,
                            null,
                            modifier = Modifier.size(56.dp),
                            tint = OnSurfaceVariant.copy(alpha = 0.4f)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            "暂无档案图片，点击上方拍照/选择图片上传",
                            style = MaterialTheme.typography.bodyMedium,
                            color = OnSurfaceVariant
                        )
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    items(images, key = { it.id ?: it.hashCode() }) { image ->
                        ArchiveImageCard(
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

@Composable
private fun ArchiveImageCard(
    image: MaterialArchiveImageDto,
    deleting: Boolean,
    onPreview: () -> Unit,
    onDelete: () -> Unit
) {
    val imageUrl = resolveImageUrl(image.url)
    val painter = rememberAsyncImagePainter(model = imageUrl)
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(SurfaceVariant)
                    .clickable { onPreview() },
                contentAlignment = Alignment.Center
            ) {
                if (imageUrl.isBlank()) {
                    Text("图片加载失败")
                } else if (painter.state is AsyncImagePainter.State.Error) {
                    Text("图片加载失败")
                } else {
                    Image(
                        painter = painter,
                        contentDescription = "档案图片",
                        modifier = Modifier.fillMaxSize(),
                        contentScale = ContentScale.Crop
                    )
                }
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "第 ${(image.sortOrder ?: 0) + 1} 张",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold
                )
                if (!image.createdAt.isNullOrBlank()) {
                    Text(
                        image.createdAt,
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant
                    )
                }
            }
            if (deleting) {
                CircularProgressIndicator(modifier = Modifier.size(22.dp), strokeWidth = 2.dp)
                Spacer(modifier = Modifier.width(8.dp))
            } else {
                TextButton(
                    onClick = onDelete,
                    colors = ButtonDefaults.textButtonColors(contentColor = Error)
                ) {
                    Icon(Icons.Outlined.Delete, null, modifier = Modifier.size(18.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("删除")
                }
            }
        }
    }
}