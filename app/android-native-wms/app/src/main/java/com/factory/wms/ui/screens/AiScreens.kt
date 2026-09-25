package com.factory.wms.ui.screens

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.provider.MediaStore
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.factory.wms.data.api.DocumentOcrResult
import com.factory.wms.data.api.RecognizeMaterialResult
import com.factory.wms.data.model.ScanLine
import com.factory.wms.ui.components.AiCaptureScaffold
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.components.WmsOutlinedActionButton
import com.factory.wms.ui.components.WmsPrimaryButton
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.util.toPositiveQtyOrNull
import com.factory.wms.ui.viewmodel.ai.AiViewModel
import com.factory.wms.ui.viewmodel.scan.ScanViewModel
import com.factory.wms.util.formatQuantity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DocumentOcrScreen(
    viewModel: AiViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var warehouseMenuExpanded by remember { mutableStateOf(false) }
    var autoCreateMaterial by remember { mutableStateOf(false) }
    // AI-APP-FIX-103：自动建档是批量不可逆写操作，提交前需二次确认。
    var showAutoCreateConfirm by remember { mutableStateOf(false) }

    // BUG-2026-08-09-004: 仓库列表仅在 OCR 识别完成、用户进入"确认生成草稿"阶段展示
    // 仓库下拉时才需要。原先在页面挂载瞬间 (`LaunchedEffect(Unit)`) 即触发 getWarehouses()，
    // 未配置 baseUrl 时 (默认 fallback http://127.0.0.1:5000/) 会立即 ConnectException，
    // 错误经 Snackbar 弹给用户，体感"页面一打开就报错"。改为仅在 ocrResult 非空时再请求。
    LaunchedEffect(uiState.ocrResult != null) {
        if (uiState.ocrResult != null) {
            viewModel.loadWarehouses()
        }
    }

    // AI-APP-FIX-405：采集区（拍照/相册/预览/空态/错误提示）统一由 AiCaptureScaffold 提供
    AiCaptureScaffold(
        title = "识别单据",
        subtitle = "拍照识别送货单/入库单等单据",
        accent = CardTeal,
        onBack = onBack,
        error = uiState.error,
        onClearError = { viewModel.clearError() },
        emptyIcon = Icons.Outlined.Description,
        emptyTitle = "拍照或选择单据图片",
        emptySubtitle = "支持送货单、入库单、出库单等\nAI自动识别并生成入库草稿",
        imageContentDescription = "单据图片",
        onImageChanged = { viewModel.clearOcrResult() }
    ) { imageUri, _ ->
        if (imageUri != null) {
            // AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton
            WmsPrimaryButton(
                text = if (uiState.isLoading) "识别中..." else "开始识别",
                onClick = {
                    coroutineScope.launch {
                        viewModel.documentOcr(uriToMultipart(imageUri, context, "image"))
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                icon = Icons.Outlined.DocumentScanner,
                color = CardTeal,
                loading = uiState.isLoading
            )
            // AI-APP-FIX-507：识别可取消——OCR 动辄十几秒，拍错图不该干等
            if (uiState.isLoading) {
                Spacer(modifier = Modifier.height(8.dp))
                WmsOutlinedActionButton(
                    text = "取消识别",
                    onClick = { viewModel.cancelOcr() },
                    modifier = Modifier.fillMaxWidth(),
                    color = CardTeal
                )
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

                    // 确认生成草稿按钮（AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton）
                    Spacer(modifier = Modifier.height(20.dp))
                    WmsPrimaryButton(
                        text = if (uiState.draftSubmitting) "生成中..." else "确认生成入库草稿",
                        onClick = {
                            if (autoCreateMaterial && unmatchedCount > 0) {
                                showAutoCreateConfirm = true
                            } else {
                                viewModel.submitInboundDraft("采购入库", autoCreateMaterial = autoCreateMaterial)
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        icon = Icons.Outlined.AssignmentTurnedIn,
                        color = CardTeal,
                        loading = uiState.draftSubmitting,
                        // AI-APP-FIX-103 / BUG-2026-09-26-003：draftResult 非空（已成功生成）后
                        // 必须保持禁用——原写法按钮恢复可点，误触即生成重复入库草稿（业务脏数据）。
                        enabled = uiState.draftResult == null &&
                            (if (autoCreateMaterial) matchedCount + unmatchedCount > 0 else matchedCount > 0)
                    )
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
                                // AI-APP-FIX-103：生成成功后提供明确出口（生成按钮此时已禁用，
                                // 防重复提交），避免页面停留状态不明导致误操作。
                                Spacer(modifier = Modifier.height(12.dp))
                                // AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton
                                WmsPrimaryButton(
                                    text = "完成，返回",
                                    onClick = onBack,
                                    modifier = Modifier.fillMaxWidth(),
                                    color = CardTeal
                                )
                            }
                        }
                    }

                    // AI-APP-FIX-103：自动建档会按识别结果批量新建物料档案（不可逆写操作），
                    // 提交前二次确认，防止误触生成错误档案。
                    if (showAutoCreateConfirm) {
                        AlertDialog(
                            onDismissRequest = { showAutoCreateConfirm = false },
                            title = { Text("确认自动建档") },
                            text = {
                                Text("将自动新建 $unmatchedCount 个物料档案，并生成入库草稿。确认继续？")
                            },
                            confirmButton = {
                                TextButton(onClick = {
                                    showAutoCreateConfirm = false
                                    viewModel.submitInboundDraft("采购入库", autoCreateMaterial = true)
                                }) { Text("确认生成") }
                            },
                            dismissButton = {
                                TextButton(onClick = { showAutoCreateConfirm = false }) { Text("取消") }
                            }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ObjectRecognizeScreen(
    viewModel: AiViewModel,
    onBack: () -> Unit,
    /**
     * AI-APP-FIX-507：识别出匹配物料后的去向 CTA（跳查库存查该物料）。
     * 此前识别结果只能"看"，看完想查库存要手动抄编码换页输入。
     */
    onQueryStock: (String) -> Unit = {}
) {
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    // AI-APP-FIX-405：采集区统一由 AiCaptureScaffold 提供
    AiCaptureScaffold(
        title = "识物",
        subtitle = "拍照识别物料，自动匹配信息",
        accent = CardPink,
        onBack = onBack,
        error = uiState.error,
        onClearError = { viewModel.clearError() },
        emptyIcon = Icons.Outlined.CameraAlt,
        emptyTitle = "拍照识别物料",
        emptySubtitle = "拍摄物料标签、实物或包装\nAI自动识别并匹配物料信息",
        imageContentDescription = "物料图片",
        onImageChanged = { viewModel.clearRecognizedMaterial() }
    ) { imageUri, _ ->
        if (imageUri != null) {
            // AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton
            WmsPrimaryButton(
                text = if (uiState.isLoading) "识别中..." else "开始识别",
                onClick = {
                    coroutineScope.launch {
                        viewModel.recognizeMaterial(uriToMultipart(imageUri, context, "image"))
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                icon = Icons.Outlined.Search,
                color = CardPink,
                loading = uiState.isLoading
            )
            // AI-APP-FIX-507：识别可取消——识别动辄十几秒，拍错图不该干等
            if (uiState.isLoading) {
                Spacer(modifier = Modifier.height(8.dp))
                WmsOutlinedActionButton(
                    text = "取消识别",
                    onClick = { viewModel.cancelRecognition() },
                    modifier = Modifier.fillMaxWidth(),
                    color = CardPink
                )
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
                                        fontSize = 16.sp,
                                        // AI-APP-FIX-508：长编码单行省略，不把库存徽标挤出屏外
                                        modifier = Modifier.weight(1f),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
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
                                    style = MaterialTheme.typography.bodyMedium,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis
                                )
                                if (!material.spec.isNullOrBlank()) {
                                    Text(
                                        "规格: ${material.spec}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = OnSurfaceVariant,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(top = 8.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
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
                                // AI-APP-FIX-507：识别结果去向 CTA——一键跳查库存查该物料，
                                // 不再靠手抄编码换页输入。
                                if (!material.code.isNullOrBlank()) {
                                    TextButton(
                                        onClick = { onQueryStock(material.code) },
                                        modifier = Modifier.align(Alignment.End)
                                    ) {
                                        Text("查该物料库存", color = CardPink)
                                        Spacer(modifier = Modifier.width(2.dp))
                                        Icon(
                                            Icons.Outlined.ChevronRight,
                                            contentDescription = null,
                                            tint = CardPink,
                                            modifier = Modifier.size(16.dp)
                                        )
                                    }
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeRecognizeScreen(
    aiViewModel: AiViewModel,
    scanViewModel: ScanViewModel,
    onBack: () -> Unit
) {
    val uiState by aiViewModel.uiState.collectAsState()
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    // 盘点实际数量（默认取识别数量，可编辑）
    var countQty by remember { mutableStateOf("1") }

    // 识别结果带出数量时作为默认盘点数量
    LaunchedEffect(uiState.recognizedMaterial) {
        val extractedQty = uiState.recognizedMaterial?.extracted?.quantity
        if (extractedQty != null && extractedQty > 0) {
            countQty = formatQuantity(extractedQty)
        }
    }

    // AI-APP-FIX-405：采集区统一由 AiCaptureScaffold 提供
    AiCaptureScaffold(
        title = "识物盘点",
        subtitle = "拍照识别物料或标签，录入盘点数量",
        accent = CardPurple,
        onBack = onBack,
        error = uiState.error,
        onClearError = { aiViewModel.clearError() },
        emptyIcon = Icons.Outlined.CameraAlt,
        emptyTitle = "拍照识别物料标签",
        emptySubtitle = "拍摄物料、标签或包装\nAI自动识别并加入盘点清单",
        imageContentDescription = "物料图片",
        onImageChanged = {
            countQty = "1"
            aiViewModel.clearRecognizedMaterial()
        }
    ) { imageUri, snackbarHostState ->
        if (imageUri != null) {
            // AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton
            WmsPrimaryButton(
                text = if (uiState.isLoading) "识别中..." else "开始识别",
                onClick = {
                    coroutineScope.launch {
                        aiViewModel.recognizeMaterial(uriToMultipart(imageUri, context, "image"))
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                icon = Icons.Outlined.AutoAwesome,
                color = CardPurple,
                loading = uiState.isLoading
            )
            // AI-APP-FIX-507：识别可取消——识别动辄十几秒，拍错图不该干等
            if (uiState.isLoading) {
                Spacer(modifier = Modifier.height(8.dp))
                WmsOutlinedActionButton(
                    text = "取消识别",
                    onClick = { aiViewModel.cancelRecognition() },
                    modifier = Modifier.fillMaxWidth(),
                    color = CardPurple
                )
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

                // AI-APP-FIX-104 / BUG-2026-09-26-004：多候选匹配不再强制取 Top1——
                // AI Top1 选错就会把数量盘到错误物料上。多候选时必须用户点选确认，
                // 未选择时"添加到盘点清单"保持禁用。
                var selectedMatchCode by remember(result) { mutableStateOf<String?>(null) }
                val matches = result.matches.orEmpty()
                val materialCode = when {
                    matches.size > 1 -> selectedMatchCode
                    matches.size == 1 -> matches.first().code
                    else -> result.extracted?.code
                }
                val matched = matches.isNotEmpty()
                val selectionPending = matches.size > 1 && selectedMatchCode == null

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

                // AI-APP-FIX-104：多候选时渲染可点选列表，用户确认要盘点的物料。
                if (matches.size > 1) {
                    Text(
                        "识别到 ${matches.size} 个候选物料，请选择要盘点的物料",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = OnSurface
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    matches.forEach { material ->
                        val selected = material.code != null && material.code == selectedMatchCode
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(16.dp))
                                .clickable { selectedMatchCode = material.code },
                            shape = RoundedCornerShape(16.dp),
                            border = if (selected) BorderStroke(2.dp, CardPurple) else null,
                            colors = CardDefaults.cardColors(
                                containerColor = if (selected) CardPurple.copy(alpha = 0.08f) else CardBackground
                            ),
                            elevation = CardDefaults.cardElevation(defaultElevation = if (selected) 0.dp else 2.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        material.code ?: "",
                                        fontWeight = FontWeight.Bold,
                                        color = Primary,
                                        fontSize = 15.sp
                                    )
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
                                }
                                if (selected) {
                                    Icon(
                                        Icons.Filled.CheckCircle,
                                        contentDescription = "已选择",
                                        tint = CardPurple,
                                        modifier = Modifier.size(24.dp)
                                    )
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }

                // 匹配状态提示
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = when {
                            selectionPending -> WarningContainer.copy(alpha = 0.5f)
                            matched -> SuccessContainer.copy(alpha = 0.5f)
                            else -> ErrorContainer.copy(alpha = 0.5f)
                        }
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            if (matched && !selectionPending) Icons.Outlined.CheckCircle
                            else Icons.Outlined.Warning,
                            null,
                            tint = when {
                                selectionPending -> Warning
                                matched -> Success
                                else -> Error
                            },
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            when {
                                selectionPending -> "存在多个候选物料，请先选择要盘点的物料"
                                matched -> "已匹配物料：${materialCode ?: ""} ${matches.firstOrNull { it.code == materialCode }?.name ?: ""}"
                                else -> "未匹配到建档物料，请确认编码后添加"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = when {
                                selectionPending -> Warning
                                matched -> Success
                                else -> Error
                            },
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
                        // AI-APP-FIX-105：非法/非正数量即时标红，配合添加按钮拦截提示。
                        isError = countQty.toPositiveQtyOrNull() == null,
                        // AI-MOB-SCAN-UX-01：识物盘点的实盘数量同样弹数字键盘。
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Decimal,
                            imeAction = ImeAction.Done
                        ),
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

                // 添加到盘点清单（AI-APP-FIX-404：自绘主按钮 → WmsPrimaryButton）
                Spacer(modifier = Modifier.height(20.dp))
                WmsPrimaryButton(
                    text = "添加到盘点清单",
                    onClick = {
                        val code = materialCode?.trim()
                        // AI-APP-FIX-105 / BUG-2026-09-26-001：非法数量必须拦截提示，
                        // 禁止 ?: 1.0 静默兜底（清空输入即按 1 盘入，现场无感知）。
                        val qty = countQty.toPositiveQtyOrNull()
                        if (code.isNullOrBlank()) {
                            coroutineScope.launch {
                                snackbarHostState.showSnackbar("无法识别物料编码，请重试或手动添加", duration = SnackbarDuration.Short)
                            }
                            return@onClick
                        }
                        if (qty == null) {
                            coroutineScope.launch {
                                snackbarHostState.showSnackbar("请输入大于 0 的有效数量", duration = SnackbarDuration.Short)
                            }
                            return@onClick
                        }
                        scanViewModel.addScanLine(ScanLine(material_code = code, quantity = qty))
                        coroutineScope.launch {
                            snackbarHostState.showSnackbar(
                                "已加入盘点清单：$code x ${formatQuantity(qty)}",
                                duration = SnackbarDuration.Short
                            )
                        }
                        onBack()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    icon = Icons.Outlined.AddCircle,
                    color = CardPurple,
                    // 多候选未选择时 materialCode == null，按钮自然禁用（状态卡同步提示先选择）。
                    enabled = materialCode != null
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
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

internal suspend fun uriToMultipart(
    uri: android.net.Uri,
    context: android.content.Context,
    partName: String
): MultipartBody.Part = withContext(Dispatchers.IO) {
    val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
        ?: throw IllegalStateException("无法读取图片")

    val compressed = if (bytes.size > 2 * 1024 * 1024) {
        // AI-APP-FIX-102：先 inJustDecodeBounds 读尺寸，再按 inSampleSize（2 的幂）降采样
        // 解码。原写法 decodeByteArray 全尺寸解码，FIX-101 后拍照可达数十 MP
        // （全尺寸 Bitmap 数百 MB），有直接 OOM 风险。
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) {
            // 尺寸无法解析（异常格式）：不重编码，原样上传交由服务端处理。
            bytes
        } else {
            val maxDim = 1920
            var sample = 1
            while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxDim) {
                sample *= 2
            }
            val decodeOpts = BitmapFactory.Options().apply { inSampleSize = sample }
            val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decodeOpts)
                ?: throw IllegalStateException("图片解码失败")
            val bos = ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, bos)
            bos.toByteArray()
        }
    } else bytes

    val requestBody = compressed.toRequestBody("image/jpeg".toMediaTypeOrNull())
    MultipartBody.Part.createFormData(partName, "image_${System.currentTimeMillis()}.jpg", requestBody)
}
