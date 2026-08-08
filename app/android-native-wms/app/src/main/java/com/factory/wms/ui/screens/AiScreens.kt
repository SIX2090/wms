package com.factory.wms.ui.screens

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import kotlinx.coroutines.launch
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.scale
import coil.compose.AsyncImage
import com.factory.wms.data.api.DocumentOcrResult
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.util.formatQuantity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.InputStream

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocumentOcrScreen(
    viewModel: AiViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var selectedImageUri by remember { mutableStateOf<android.net.Uri?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()
    var warehouseMenuExpanded by remember { mutableStateOf(false) }
    var autoCreateMaterial by remember { mutableStateOf(false) }

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            selectedImageUri = it
            viewModel.clearOcrResult()
        }
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap ->
        bitmap?.let {
            val path = android.provider.MediaStore.Images.Media.insertImage(
                context.contentResolver, it, "ocr_${System.currentTimeMillis()}", null
            )
            selectedImageUri = android.net.Uri.parse(path)
            viewModel.clearOcrResult()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    LaunchedEffect(Unit) {
        viewModel.loadWarehouses()
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("识别单据", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "拍照识别送货单/入库单等单据",
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
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            if (selectedImageUri != null) {
                // Image preview
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Box(modifier = Modifier.fillMaxWidth()) {
                        AsyncImage(
                            model = selectedImageUri,
                            contentDescription = "单据图片",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(240.dp)
                                .clip(RoundedCornerShape(20.dp)),
                            contentScale = ContentScale.Fit
                        )
                        // Clear button
                        IconButton(
                            onClick = {
                                selectedImageUri = null
                                viewModel.clearOcrResult()
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

                // Recognize button
                Button(
                    onClick = {
                        selectedImageUri?.let { uri ->
                            coroutineScope.launch {
                                viewModel.documentOcr(uriToMultipart(uri, context, "image"))
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !uiState.isLoading,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardTeal)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("识别中...", fontSize = 16.sp)
                    } else {
                        Icon(Icons.Outlined.DocumentScanner, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("开始识别", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            } else {
                // Empty state
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        // Dashed border icon container
                        Box(
                            modifier = Modifier
                                .size(100.dp)
                                .clip(RoundedCornerShape(24.dp))
                                .border(
                                    width = 2.dp,
                                    color = CardTeal.copy(alpha = 0.3f),
                                    shape = RoundedCornerShape(24.dp)
                                )
                                .background(CardTeal.copy(alpha = 0.04f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Outlined.Description,
                                null,
                                modifier = Modifier.size(48.dp),
                                tint = CardTeal.copy(alpha = 0.6f)
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                        Text(
                            "拍照或选择单据图片",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = OnSurface
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "支持送货单、入库单、出库单等\nAI自动识别并生成入库草稿",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant,
                            textAlign = TextAlign.Center,
                            lineHeight = 20.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Action buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = { cameraLauncher.launch(null) },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = CardTeal
                        ),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardTeal.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.CameraAlt, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("拍照", fontWeight = FontWeight.Medium)
                    }
                    OutlinedButton(
                        onClick = { imagePicker.launch("image/*") },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = CardTeal
                        ),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardTeal.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.PhotoLibrary, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("选择图片", fontWeight = FontWeight.Medium)
                    }
                }
            }

            // OCR Results
            uiState.ocrResult?.let { result ->
                Spacer(modifier = Modifier.height(20.dp))
                Text(
                    "识别结果",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(10.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        if (!result.supplier.isNullOrBlank()) {
                            OcrResultRow("供应商", result.supplier)
                        }
                        if (!result.order_no.isNullOrBlank()) {
                            OcrResultRow("单据编号", result.order_no)
                        }
                        if (!result.document_type.isNullOrBlank()) {
                            OcrResultRow("单据类型", docTypeLabel(result.document_type))
                        }
                        if (!result.date.isNullOrBlank()) {
                            OcrResultRow("日期", result.date)
                        }

                        if (!result.items.isNullOrEmpty()) {
                            Spacer(modifier = Modifier.height(16.dp))
                            HorizontalDivider(color = SurfaceVariant, thickness = 1.dp)
                            Spacer(modifier = Modifier.height(14.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    "物料明细",
                                    style = MaterialTheme.typography.labelLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Primary
                                )
                                Surface(
                                    shape = RoundedCornerShape(20.dp),
                                    color = PrimaryContainer
                                ) {
                                    Text(
                                        "${result.items.size} 项",
                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                                        color = Primary,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(10.dp))

                            result.items.forEachIndexed { index, item ->
                                Card(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(14.dp),
                                    colors = CardDefaults.cardColors(
                                        containerColor = SurfaceVariant.copy(alpha = 0.5f)
                                    ),
                                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(14.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                item.name ?: item.code ?: "物料 ${index + 1}",
                                                fontWeight = FontWeight.SemiBold,
                                                fontSize = 14.sp
                                            )
                                            if (!item.spec.isNullOrBlank()) {
                                                Text(
                                                    "规格: ${item.spec}",
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = OnSurfaceVariant
                                                )
                                            }
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.padding(top = 4.dp)
                                            ) {
                                                Surface(
                                                    shape = RoundedCornerShape(6.dp),
                                                    color = if (item.matched == true) PrimaryContainer
                                                    else ErrorContainer.copy(alpha = 0.6f)
                                                ) {
                                                    Text(
                                                        if (item.matched == true) "已匹配" else "未建档",
                                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                                        color = if (item.matched == true) Primary else Error,
                                                        fontSize = 11.sp,
                                                        fontWeight = FontWeight.SemiBold
                                                    )
                                                }
                                            }
                                        }
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(8.dp))
                                                .background(PrimaryContainer),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Text(
                                                "x${formatQuantity(item.quantity ?: 1.0)}",
                                                color = Primary,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 14.sp,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp)
                                            )
                                        }
                                    }
                                }
                                if (index < result.items.size - 1) {
                                    Spacer(modifier = Modifier.height(8.dp))
                                }
                            }
                        }
                    }
                }
            }

            // AI reply text
            uiState.ocrReply?.let { reply ->
                if (reply.isNotBlank() && uiState.ocrResult?.items == null) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = InfoContainer.copy(alpha = 0.5f)
                        ),
                        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Outlined.Info,
                                    null,
                                    tint = Info,
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    "AI 识别详情",
                                    style = MaterialTheme.typography.labelLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = Info
                                )
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                reply,
                                style = MaterialTheme.typography.bodyMedium,
                                color = OnSurfaceVariant
                            )
                        }
                    }
                }
            }

// 确认识别结果 -> 生成入库草稿
            uiState.ocrResult?.let { result ->
                if (!result.items.isNullOrEmpty()) {
                    val unmatchedCount = result.items.count { it.matched != true }
                    val matchedCount = result.items.count { it.matched == true }

                    // 未匹配物料拦截提示
                    if (unmatchedCount > 0) {
                        Spacer(modifier = Modifier.height(16.dp))
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = ErrorContainer.copy(alpha = 0.5f)
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Outlined.Warning,
                                        null,
                                        tint = Error,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "存在 $unmatchedCount 行未建档物料",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Error
                                    )
                                }
                                Spacer(modifier = Modifier.height(6.dp))
                                Text(
                                    "存在 $unmatchedCount 行未匹配到建档物料。开启自动建档后，将按识别出的名称/规格自动建立物料档案并生成入库草稿；不开启则这些行会被拦截。",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = OnSurfaceVariant,
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }

                    // 仓库选择
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        "选择入库仓库",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = OnSurface
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    ExposedDropdownMenuBox(
                        expanded = warehouseMenuExpanded,
                        onExpandedChange = { warehouseMenuExpanded = it }
                    ) {
                        OutlinedButton(
                            onClick = { warehouseMenuExpanded = true },
                            modifier = Modifier
                                .fillMaxWidth()
                                .menuAnchor(),
                            shape = RoundedCornerShape(14.dp)
                        ) {
                            Icon(
                                Icons.Outlined.Warehouse,
                                null,
                                tint = Primary,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                uiState.selectedWarehouse?.let { "${it.name} (${it.code})" }
                                    ?: "选择仓库",
                                modifier = Modifier.weight(1f),
                                fontWeight = FontWeight.Medium
                            )
                            Icon(Icons.Filled.ArrowDropDown, null, tint = OnSurfaceVariant)
                        }
                        ExposedDropdownMenu(
                            expanded = warehouseMenuExpanded,
                            onDismissRequest = { warehouseMenuExpanded = false }
                        ) {
                            if (uiState.warehouses.isEmpty()) {
                                DropdownMenuItem(
                                    text = { Text("暂无可用仓库") },
                                    onClick = { warehouseMenuExpanded = false }
                                )
                            } else {
                                uiState.warehouses.forEach { wh ->
                                    DropdownMenuItem(
                                        text = { Text("${wh.name} (${wh.code})") },
                                        onClick = {
                                            viewModel.selectWarehouse(wh)
                                            warehouseMenuExpanded = false
                                        }
                                    )
                                }
                            }
                        }
                    }

                    // 自动建档开关
                    Spacer(modifier = Modifier.height(16.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        color = SurfaceVariant.copy(alpha = 0.5f)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Outlined.AutoAwesome,
                                null,
                                tint = Primary,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    "自动建档未识别物料",
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.SemiBold,
                                    color = OnSurface
                                )
                                Text(
                                    "未建档的识别行按识别名称/规格自动建立物料档案",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = OnSurfaceVariant
                                )
                            }
                            Switch(
                                checked = autoCreateMaterial,
                                onCheckedChange = { autoCreateMaterial = it }
                            )
                        }
                    }

                    // 确认生成草稿按钮
                    Spacer(modifier = Modifier.height(20.dp))
                    Button(
                        onClick = { viewModel.submitInboundDraft("采购入库", autoCreateMaterial = autoCreateMaterial) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        enabled = !uiState.draftSubmitting &&
                            (if (autoCreateMaterial) matchedCount + unmatchedCount > 0 else matchedCount > 0),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = CardTeal)
                    ) {
                        if (uiState.draftSubmitting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(22.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                            Spacer(Modifier.width(8.dp))
                            Text("生成中...", fontSize = 16.sp)
                        } else {
                            Icon(Icons.Outlined.AssignmentTurnedIn, null, modifier = Modifier.size(20.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("确认生成入库草稿", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                        }
                    }
                    Text(
                        "确认后生成 pending 草稿，不直接加库存，需在 WEB 端人工复核后正式入库。",
                        modifier = Modifier.padding(top = 8.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariant
                    )

                    // 草稿生成结果
                    uiState.draftResult?.let { draft ->
                        Spacer(modifier = Modifier.height(16.dp))
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = PrimaryContainer.copy(alpha = 0.5f)
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Filled.CheckCircle,
                                        null,
                                        tint = Primary,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "入库草稿已生成",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Primary
                                    )
                                }
                                draft.orderNo?.let {
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        "单号：$it（状态：${draft.status ?: "pending"}）",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = OnSurfaceVariant
                                    )
                                }
                                if (!draft.items.isNullOrEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        "共 ${draft.items.size} 行物料",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant
                                    )
                                }
                                if (!draft.autoCreated.isNullOrEmpty()) {
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        "自动建档 ${draft.autoCreated.size} 个物料：${draft.autoCreated.joinToString("、") { "${it.name ?: ""}(${it.code ?: ""})" }}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = Primary,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ObjectRecognizeScreen(
    viewModel: AiViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    var selectedImageUri by remember { mutableStateOf<android.net.Uri?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            selectedImageUri = it
            viewModel.clearRecognizedMaterial()
        }
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap ->
        bitmap?.let {
            val path = android.provider.MediaStore.Images.Media.insertImage(
                context.contentResolver, it, "mat_${System.currentTimeMillis()}", null
            )
            selectedImageUri = android.net.Uri.parse(path)
            viewModel.clearRecognizedMaterial()
        }
    }

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
                        Text("识物", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "拍照识别物料，自动匹配信息",
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
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            if (selectedImageUri != null) {
                // Image preview
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Box(modifier = Modifier.fillMaxWidth()) {
                        AsyncImage(
                            model = selectedImageUri,
                            contentDescription = "物料图片",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(240.dp)
                                .clip(RoundedCornerShape(20.dp)),
                            contentScale = ContentScale.Fit
                        )
                        IconButton(
                            onClick = {
                                selectedImageUri = null
                                viewModel.clearRecognizedMaterial()
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

                Button(
                    onClick = {
                        selectedImageUri?.let { uri ->
                            coroutineScope.launch {
                                viewModel.recognizeMaterial(uriToMultipart(uri, context, "image"))
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !uiState.isLoading,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPink)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("识别中...", fontSize = 16.sp)
                    } else {
                        Icon(Icons.Outlined.Search, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("开始识别", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            } else {
                // Empty state
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Box(
                            modifier = Modifier
                                .size(100.dp)
                                .clip(RoundedCornerShape(24.dp))
                                .border(
                                    width = 2.dp,
                                    color = CardPink.copy(alpha = 0.3f),
                                    shape = RoundedCornerShape(24.dp)
                                )
                                .background(CardPink.copy(alpha = 0.04f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Outlined.CameraAlt,
                                null,
                                modifier = Modifier.size(48.dp),
                                tint = CardPink.copy(alpha = 0.6f)
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                        Text(
                            "拍照识别物料",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = OnSurface
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "拍摄物料标签、实物或包装\nAI自动识别并匹配物料信息",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant,
                            textAlign = TextAlign.Center,
                            lineHeight = 20.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = { cameraLauncher.launch(null) },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = CardPink),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardPink.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.CameraAlt, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("拍照", fontWeight = FontWeight.Medium)
                    }
                    OutlinedButton(
                        onClick = { imagePicker.launch("image/*") },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = CardPink),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardPink.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.PhotoLibrary, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("选择图片", fontWeight = FontWeight.Medium)
                    }
                }
            }

            // Recognition results
            uiState.recognizedMaterial?.let { result ->
                Spacer(modifier = Modifier.height(20.dp))
                Text(
                    "识别结果",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(10.dp))

                // Extracted info
                result.extracted?.let { extracted ->
                    if (extracted.code != null || extracted.name != null) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = CardPink.copy(alpha = 0.04f)
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Outlined.AutoAwesome,
                                        null,
                                        tint = CardPink,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "AI 提取信息",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = CardPink
                                    )
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                                extracted.code?.let { OcrResultRow("物料编码", it) }
                                extracted.name?.let { OcrResultRow("物料名称", it) }
                                extracted.spec?.let { OcrResultRow("规格型号", it) }
                                extracted.description?.let { OcrResultRow("外观特征", it) }
                                extracted.quantity?.let { OcrResultRow("数量", formatQuantity(it)) }
                                extracted.confidence?.let {
                                    OcrResultRow("置信度", "${"%.0f".format(it * 100)}%")
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                }

                // Matched materials
                if (!result.matches.isNullOrEmpty()) {
                    Text(
                        "匹配物料 (${result.matches.size} 项)",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    result.matches.forEach { material ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                            colors = CardDefaults.cardColors(containerColor = CardBackground)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        material.code ?: "",
                                        fontWeight = FontWeight.Bold,
                                        color = Primary,
                                        fontSize = 16.sp
                                    )
                                    Surface(
                                        shape = RoundedCornerShape(20.dp),
                                        color = if ((material.stock ?: 0.0) > (material.minStock ?: 0.0))
                                            SuccessContainer else ErrorContainer
                                    ) {
                                        Text(
                                            "库存: ${formatQuantity(material.stock ?: 0.0)}",
                                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                                            fontSize = 12.sp,
                                            fontWeight = FontWeight.Medium,
                                            color = if ((material.stock ?: 0.0) > (material.minStock ?: 0.0))
                                                Success else Error
                                        )
                                    }
                                }
                                Text(
                                    material.name ?: "",
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                if (!material.spec.isNullOrBlank()) {
                                    Text(
                                        "规格: ${material.spec}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant
                                    )
                                }
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 8.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Text(
                                        "${material.unit ?: ""} · ${material.category ?: ""}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant
                                    )
                                    Text(
                                        "¥${"%.2f".format(material.price ?: 0.0)}",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = OnSurface
                                    )
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }

                result.reply?.let { reply ->
                    if (reply.isNotBlank()) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = InfoContainer.copy(alpha = 0.5f)
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Outlined.Info,
                                        null,
                                        tint = Info,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "AI 识别详情",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Info
                                    )
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    reply,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = OnSurfaceVariant
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeRecognizeScreen(
    aiViewModel: AiViewModel,
    scanViewModel: ScanViewModel,
    onBack: () -> Unit
) {
    val uiState by aiViewModel.uiState.collectAsState()
    val context = LocalContext.current
    var selectedImageUri by remember { mutableStateOf<android.net.Uri?>(null) }
    // 盘点实际数量（默认取识别数量，可编辑）
    var countQty by remember { mutableStateOf("1") }
    val snackbarHostState = remember { SnackbarHostState() }
    val coroutineScope = rememberCoroutineScope()

    val imagePicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            selectedImageUri = it
            countQty = "1"
            aiViewModel.clearRecognizedMaterial()
        }
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicturePreview()
    ) { bitmap ->
        bitmap?.let {
            val path = android.provider.MediaStore.Images.Media.insertImage(
                context.contentResolver, it, "stk_${System.currentTimeMillis()}", null
            )
            selectedImageUri = android.net.Uri.parse(path)
            countQty = "1"
            aiViewModel.clearRecognizedMaterial()
        }
    }

    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            aiViewModel.clearError()
        }
    }

    // 识别结果带出数量时作为默认盘点数量
    LaunchedEffect(uiState.recognizedMaterial) {
        val extractedQty = uiState.recognizedMaterial?.extracted?.quantity
        if (extractedQty != null && extractedQty > 0) {
            countQty = formatQuantity(extractedQty)
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = Background,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("识物盘点", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text(
                            "拍照识别物料或标签，录入盘点数量",
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
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            if (selectedImageUri != null) {
                // Image preview
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground)
                ) {
                    Box(modifier = Modifier.fillMaxWidth()) {
                        AsyncImage(
                            model = selectedImageUri,
                            contentDescription = "物料图片",
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(240.dp)
                                .clip(RoundedCornerShape(20.dp)),
                            contentScale = ContentScale.Fit
                        )
                        IconButton(
                            onClick = {
                                selectedImageUri = null
                                aiViewModel.clearRecognizedMaterial()
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

                Button(
                    onClick = {
                        selectedImageUri?.let { uri ->
                            coroutineScope.launch {
                                aiViewModel.recognizeMaterial(uriToMultipart(uri, context, "image"))
                            }
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !uiState.isLoading,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPurple)
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("识别中...", fontSize = 16.sp)
                    } else {
                        Icon(Icons.Outlined.AutoAwesome, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("开始识别", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            } else {
                // Empty state
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = CardBackground),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Box(
                            modifier = Modifier
                                .size(100.dp)
                                .clip(RoundedCornerShape(24.dp))
                                .border(
                                    width = 2.dp,
                                    color = CardPurple.copy(alpha = 0.3f),
                                    shape = RoundedCornerShape(24.dp)
                                )
                                .background(CardPurple.copy(alpha = 0.04f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                Icons.Outlined.CameraAlt,
                                null,
                                modifier = Modifier.size(48.dp),
                                tint = CardPurple.copy(alpha = 0.6f)
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                        Text(
                            "拍照识别物料标签",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = OnSurface
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "拍摄物料、标签或包装\nAI自动识别并加入盘点清单",
                            style = MaterialTheme.typography.bodySmall,
                            color = OnSurfaceVariant,
                            textAlign = TextAlign.Center,
                            lineHeight = 20.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = { cameraLauncher.launch(null) },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = CardPurple),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardPurple.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.CameraAlt, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("拍照", fontWeight = FontWeight.Medium)
                    }
                    OutlinedButton(
                        onClick = { imagePicker.launch("image/*") },
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = CardPurple),
                        border = ButtonDefaults.outlinedButtonBorder.copy(
                            brush = androidx.compose.ui.graphics.SolidColor(CardPurple.copy(alpha = 0.3f))
                        )
                    ) {
                        Icon(Icons.Outlined.PhotoLibrary, null, modifier = Modifier.size(20.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("选择图片", fontWeight = FontWeight.Medium)
                    }
                }
            }

            // Recognition results
            uiState.recognizedMaterial?.let { result ->
                Spacer(modifier = Modifier.height(20.dp))
                Text(
                    "识别结果",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(10.dp))

                // 确定加入盘点的物料编码：优先已建档匹配，回退到识别编码
                val materialCode = result.matches?.firstOrNull()?.code
                    ?: result.extracted?.code
                val matched = !result.matches.isNullOrEmpty()

                // Extracted info
                result.extracted?.let { extracted ->
                    if (extracted.code != null || extracted.name != null || extracted.spec != null) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = CardPurple.copy(alpha = 0.04f)
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Outlined.AutoAwesome,
                                        null,
                                        tint = CardPurple,
                                        modifier = Modifier.size(20.dp)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        "AI 提取信息",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.SemiBold,
                                        color = CardPurple
                                    )
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                                extracted.code?.let { OcrResultRow("物料编码", it) }
                                extracted.name?.let { OcrResultRow("物料名称", it) }
                                extracted.spec?.let { OcrResultRow("规格型号", it) }
                                extracted.description?.let { OcrResultRow("外观特征", it) }
                                extracted.confidence?.let {
                                    OcrResultRow("置信度", "${"%.0f".format(it * 100)}%")
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                }

                // 匹配状态提示
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (matched) SuccessContainer.copy(alpha = 0.5f)
                        else ErrorContainer.copy(alpha = 0.5f)
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            if (matched) Icons.Outlined.CheckCircle else Icons.Outlined.Warning,
                            null,
                            tint = if (matched) Success else Error,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            if (matched) {
                                "已匹配物料：${result.matches?.firstOrNull()?.code ?: ""} ${result.matches?.firstOrNull()?.name ?: ""}"
                            } else {
                                "未匹配到建档物料，请确认编码后添加"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = if (matched) Success else Error,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                // 数量输入
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    "盘点实际数量",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = OnSurface
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    FilledIconButton(
                        onClick = {
                            val current = countQty.toDoubleOrNull() ?: 1.0
                            countQty = formatQuantity((current - 1).coerceAtLeast(0.0))
                        },
                        modifier = Modifier.size(44.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = CardPurple.copy(alpha = 0.1f)
                        )
                    ) {
                        Icon(
                            Icons.Outlined.Remove,
                            "减1",
                            tint = CardPurple,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    OutlinedTextField(
                        value = countQty,
                        onValueChange = { countQty = it },
                        label = { Text("数量") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = CardPurple,
                            focusedLabelColor = CardPurple
                        )
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    FilledIconButton(
                        onClick = {
                            val current = countQty.toDoubleOrNull() ?: 0.0
                            countQty = formatQuantity(current + 1)
                        },
                        modifier = Modifier.size(44.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = CardPurple
                        )
                    ) {
                        Icon(
                            Icons.Outlined.Add,
                            "加1",
                            tint = Color.White,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }

                // 添加到盘点清单
                Spacer(modifier = Modifier.height(20.dp))
                Button(
                    onClick = {
                        val code = materialCode?.trim()
                        val qty = countQty.toDoubleOrNull() ?: 1.0
                        if (code.isNullOrBlank()) {
                            snackbarHostState.showSnackbar("无法识别物料编码，请重试或手动添加", duration = SnackbarDuration.Short)
                            return@Button
                        }
                        scanViewModel.addScanLine(ScanLine(material_code = code, quantity = qty))
                        snackbarHostState.showSnackbar(
                            "已加入盘点清单：$code x ${formatQuantity(qty)}",
                            duration = SnackbarDuration.Short
                        )
                        onBack()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = materialCode != null,
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = CardPurple)
                ) {
                    Icon(Icons.Outlined.AddCircle, null, modifier = Modifier.size(20.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("添加到盘点清单", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun OcrResultRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 5.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = OnSurfaceVariant
        )
        Text(
            value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = OnSurface,
            textAlign = TextAlign.End,
            modifier = Modifier.widthIn(max = 200.dp)
        )
    }
}

private fun docTypeLabel(type: String?): String = when (type) {
    "in_order" -> "入库单 / 送货单"
    "out_order" -> "出库单 / 领料单"
    "transfer" -> "调拨单"
    "check" -> "盘点单"
    "wechat" -> "微信通知"
    else -> type ?: "未知"
}

private suspend fun uriToMultipart(
    uri: android.net.Uri,
    context: android.content.Context,
    partName: String
): MultipartBody.Part = withContext(Dispatchers.IO) {
    val inputStream: InputStream = context.contentResolver.openInputStream(uri)
        ?: throw IllegalStateException("无法读取图片")
    val bytes = inputStream.use { it.readBytes() }

    val compressed = if (bytes.size > 2 * 1024 * 1024) {
        val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        val maxDim = 1200
        val scaled = if (bitmap.width > maxDim || bitmap.height > maxDim) {
            val ratio = minOf(maxDim.toFloat() / bitmap.width, maxDim.toFloat() / bitmap.height)
            bitmap.scale((bitmap.width * ratio).toInt(), (bitmap.height * ratio).toInt())
        } else bitmap
        val bos = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 80, bos)
        bos.toByteArray()
    } else bytes

    val requestBody = compressed.toRequestBody("image/jpeg".toMediaTypeOrNull())
    MultipartBody.Part.createFormData(partName, "image_${System.currentTimeMillis()}.jpg", requestBody)
}