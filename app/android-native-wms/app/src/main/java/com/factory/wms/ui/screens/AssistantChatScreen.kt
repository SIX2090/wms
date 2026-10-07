package com.factory.wms.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DeleteSweep
import androidx.compose.material.icons.outlined.Image
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.compose.runtime.saveable.rememberSaveable
import com.factory.wms.ui.components.StatusBarIconEffect
import com.factory.wms.ui.components.WmsGradientHeader
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.ai.AssistantChatMessage
import com.factory.wms.ui.viewmodel.ai.AssistantChatViewModel
import com.factory.wms.ui.viewmodel.ai.AssistantVoiceInputViewModel
import kotlinx.coroutines.launch
import java.io.ByteArrayOutputStream
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.provider.OpenableColumns
import android.util.Base64
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.factory.wms.ui.components.rememberCameraLauncherWithPermission
import kotlinx.coroutines.Dispatchers

/**
 * AI-ASSISTANT-MOBILE-001：App 端 AI 助手聊天页。
 *
 * 与 PC AI 助手同一后端链路（28 个意图）：查库存、查单号、今日概况、
 * 建单草稿引导、库存分析问答。所有理解在服务端完成，本地零解析。
 *
 * AI-ASSISTANT-VOICE-001：输入区新增语音输入——复用语音指令链的
 * [com.factory.wms.ui.viewmodel.voice.VoiceSttEngine] 三级引擎回退
 * （云 ASR → sherpa 本地 → 系统识别），识别文本回填输入框（不自动发送，
 * 用户可修改后手动发送）。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AssistantChatScreen(
    viewModel: AssistantChatViewModel,
    voiceViewModel: AssistantVoiceInputViewModel,
    onBack: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsState()
    val voiceState by voiceViewModel.uiState.collectAsState()
    var input by rememberSaveable { mutableStateOf("") }
    var showClearConfirm by rememberSaveable { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    StatusBarIconEffect(darkIcons = false)

    // AUDIT-2026-10-07-009-P1：相机改用全尺寸拍照（TakePicture + FileProvider），
    // 不再用低清缩略图契约（送货单小字识别需要全分辨率）。
    // 复用 components/CameraLauncher.kt（含权限申请与 OEM 兼容授权，ScanScreenBase 同款）。
    val cameraCapture = rememberCameraLauncherWithPermission(snackbarHostState) { uri: Uri ->
        scope.launch(Dispatchers.IO) {
            runCatching {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    BitmapFactory.decodeStream(input)
                }
            }.getOrNull()?.let { bitmap ->
                // 限制最长边 1600px：送货单细节保留 + 控制上传体积（base64 后 ~1MB 内）
                val maxSide = 1600
                val scaled = if (bitmap.width > maxSide || bitmap.height > maxSide) {
                    val scale = maxSide.toFloat() / maxOf(bitmap.width, bitmap.height)
                    Bitmap.createScaledBitmap(
                        bitmap,
                        (bitmap.width * scale).toInt().coerceAtLeast(1),
                        (bitmap.height * scale).toInt().coerceAtLeast(1),
                        true
                    )
                } else {
                    bitmap
                }
                val baos = ByteArrayOutputStream()
                scaled.compress(Bitmap.CompressFormat.JPEG, 85, baos)
                val base64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
                scope.launch { viewModel.setPendingImage(base64) }
            }
        }
    }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch(Dispatchers.IO) {
                val bytes = runCatching {
                    context.contentResolver.openInputStream(it)?.use { input -> input.readBytes() }
                }.getOrNull() ?: return@launch
                val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                scope.launch { viewModel.setPendingImage(base64) }
            }
        }
    }

    val fileLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        uri?.let {
            scope.launch(Dispatchers.IO) {
                // AUDIT-2026-10-07-009-P1：文件名从 ContentResolver 查 DISPLAY_NAME。
                // uri.lastPathSegment 在 content:// URI 下返回 provider 内部 ID（如 msf:76），
                // 不带扩展名 → 后端按扩展名路由解析会直接拒绝。
                val fileName = runCatching {
                    context.contentResolver.query(it, null, null, null, null)?.use { cursor ->
                        val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (idx >= 0 && cursor.moveToFirst()) cursor.getString(idx) else null
                    }
                }.getOrNull() ?: it.lastPathSegment ?: "文件"

                val bytes = runCatching {
                    context.contentResolver.openInputStream(it)?.use { input -> input.readBytes() }
                }.getOrNull() ?: return@launch

                val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                scope.launch { viewModel.setPendingFile(base64, fileName) }
            }
        }
    }

    // 麦克风权限：授权后立即开录；拒绝则提示
    val micPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            voiceViewModel.startListening(context)
        } else {
            voiceViewModel.stopListening()
            voiceViewModel.clearResult()
            scope.launch { snackbarHostState.showSnackbar("需要麦克风权限才能使用语音输入") }
        }
    }

    // AI-ASSISTANT-VOICE-001：识别完成的文本回填输入框（追加在已有文本后，
    // 便于连续口述分段补充；不自动发送——ASR 可能有误，用户过目再发）
    LaunchedEffect(Unit) {
        voiceViewModel.recognizedText.collect { text ->
            input = if (input.isBlank()) text else "$input$text"
        }
    }

    // 语音输入错误提示（识别失败/无权限/引擎不可用/超时）
    LaunchedEffect(voiceState.error) {
        voiceState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            voiceViewModel.clearResult()
        }
    }

    // 新消息到达或加载态变化时滚到底部
    LaunchedEffect(uiState.messages.size, uiState.isLoading) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }
    LaunchedEffect(uiState.error) {
        uiState.error?.let {
            snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
            viewModel.clearError()
        }
    }

    // AUDIT-2026-10-07-P6：发送失败的消息退回输入框（不覆盖用户已输入的新内容）
    LaunchedEffect(uiState.failedDraft) {
        uiState.failedDraft?.let { draft ->
            if (input.isBlank()) {
                input = draft
            }
            viewModel.consumeFailedDraft()
        }
    }

    // FEATURE-2026-10-07-010：剪贴板图片检测——App 切回前台时查剪贴板，
    // 发现 image URI 就提示「点此添加为附件」（对标 PC 端 Ctrl+V 贴图能力）。
    // Android 12+ 系统会弹剪贴板访问提示，属正常行为。
    val clipboardImageDetected = remember { mutableStateOf<Uri?>(null) }
    val lastClipboardPromptedUri = remember { mutableStateOf<Uri?>(null) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                val alreadyHasAttachment = viewModel.uiState.value.pendingImage != null ||
                        viewModel.uiState.value.pendingFile != null
                if (!alreadyHasAttachment) {
                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                    val clip = cm?.primaryClip
                    if (clip != null && clip.itemCount > 0) {
                        val uri = clip.getItemAt(0).uri
                        val hasImage = clip.description?.hasMimeType("image/") == true ||
                                (uri != null && context.contentResolver.getType(uri)?.startsWith("image/") == true)
                        // 同一 URI 只提示一次（用户拒绝后不再烦人）
                        if (hasImage && uri != null && uri != lastClipboardPromptedUri.value) {
                            lastClipboardPromptedUri.value = uri
                            clipboardImageDetected.value = uri
                        }
                    }
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    if (clipboardImageDetected.value != null) {
        val clipUri = clipboardImageDetected.value
        LaunchedEffect(clipUri) {
            val result = snackbarHostState.showSnackbar(
                message = "检测到剪贴板图片，添加为附件？",
                actionLabel = "添加",
                duration = SnackbarDuration.Indefinite
            )
            if (result == SnackbarResult.ActionPerformed) {
                scope.launch(Dispatchers.IO) {
                    val bytes = runCatching {
                        context.contentResolver.openInputStream(clipUri!!)?.use { it.readBytes() }
                    }.getOrNull()
                    if (bytes != null) {
                        val base64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                        scope.launch { viewModel.setPendingImage(base64) }
                    }
                }
            }
            clipboardImageDetected.value = null
        }
    }

    Scaffold(
        containerColor = Background,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            WmsGradientHeader(
                title = "AI 助手",
                subtitle = "查库存 · 查单号 · 今日概况 · 分析问答",
                accent = Primary,
                onBack = onBack,
                trailing = {
                    IconButton(onClick = {
                        // AUDIT-2026-10-07-P5：清空前确认——误触即丢整段对话且无恢复入口
                        if (uiState.messages.isNotEmpty()) {
                            showClearConfirm = true
                        }
                    }) {
                        Icon(
                            Icons.Outlined.DeleteSweep,
                            contentDescription = "清空对话",
                            tint = Color.White
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                if (uiState.messages.isEmpty()) {
                    item { AssistantEmptyHint() }
                }
                items(uiState.messages, key = { it.id }) { message ->
                    AssistantMessageBubble(message)
                }
                if (uiState.isLoading) {
                    item {
                        AssistantTypingBubble()
                    }
                }
            }

            // AUDIT-2026-10-07-009-P2：附件预览条——拍照/选文件后必须有可视反馈，
            // 否则用户不知道附件是否选上（原实现选完界面无任何变化）。
            if (uiState.pendingImage != null || uiState.pendingFile != null) {
                Surface(
                    color = SurfaceVariant.copy(alpha = 0.4f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Outlined.Image,
                            contentDescription = null,
                            tint = Primary,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = when {
                                uiState.pendingFile != null -> "已选文件：${uiState.pendingFile?.second ?: ""}"
                                else -> "已选图片（发送时随消息上传）"
                            },
                            fontSize = 13.sp,
                            color = OnSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f)
                        )
                        TextButton(onClick = { viewModel.clearPendingAttachments() }) {
                            Text("移除", color = Error, fontSize = 13.sp)
                        }
                    }
                }
            }

            // 输入区
            Surface(
                color = CardBackground,
                tonalElevation = 2.dp
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                        .navigationBarsPadding(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // BUG-2026-10-07-009：+ 按钮（相机/相册/文件）
                    var showAttachMenu by remember { mutableStateOf(false) }
                    Box {
                        FilledIconButton(
                            onClick = { showAttachMenu = true },
                            shape = RoundedCornerShape(50),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = CardBackground,
                                contentColor = Primary
                            )
                        ) {
                            Icon(
                                Icons.Outlined.Add,
                                contentDescription = "附件",
                                modifier = Modifier.size(20.dp)
                            )
                        }
                        DropdownMenu(
                            expanded = showAttachMenu,
                            onDismissRequest = { showAttachMenu = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("拍照") },
                                onClick = {
                                    showAttachMenu = false
                                    cameraCapture()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("相册") },
                                onClick = {
                                    showAttachMenu = false
                                    galleryLauncher.launch("image/*")
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("文件") },
                                onClick = {
                                    showAttachMenu = false
                                    fileLauncher.launch("*/*")
                                }
                            )
                        }
                    }
                    Spacer(Modifier.width(8.dp))
                    // AI-ASSISTANT-VOICE-001：语音输入按钮——录音中变停止按钮
                    FilledIconButton(
                        onClick = {
                            if (voiceState.isListening) {
                                voiceViewModel.stopListening()
                            } else {
                                val granted = ContextCompat.checkSelfPermission(
                                    context, Manifest.permission.RECORD_AUDIO
                                ) == PackageManager.PERMISSION_GRANTED
                                if (granted) {
                                    voiceViewModel.startListening(context)
                                } else {
                                    micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                }
                            }
                        },
                        shape = RoundedCornerShape(50),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = if (voiceState.isListening) Error else CardBackground,
                            contentColor = if (voiceState.isListening) Color.White else Primary
                        )
                    ) {
                        if (voiceState.isListening) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = Color.White,
                                strokeWidth = 2.dp
                            )
                        } else {
                            Icon(
                                Icons.Outlined.Mic,
                                contentDescription = "语音输入",
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedTextField(
                        value = input,
                        onValueChange = { if (it.length <= 2000) input = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("问我任何仓库问题…", fontSize = 14.sp) },
                        shape = RoundedCornerShape(22.dp),
                        maxLines = 4,
                        textStyle = MaterialTheme.typography.bodyMedium,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                viewModel.send(input)
                                input = ""
                            }
                        ),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Primary,
                            unfocusedBorderColor = SurfaceVariant
                        )
                    )
                    Spacer(Modifier.width(8.dp))
                    FilledIconButton(
                        onClick = {
                            viewModel.send(input)
                            input = ""
                        },
                        enabled = (input.isNotBlank() || uiState.pendingImage != null || uiState.pendingFile != null) && !uiState.isLoading,
                        shape = RoundedCornerShape(50),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = Primary,
                            contentColor = Color.White,
                            disabledContainerColor = Primary.copy(alpha = 0.35f)
                        )
                    ) {
                        Icon(
                            Icons.AutoMirrored.Outlined.Send,
                            contentDescription = "发送",
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }

        // AUDIT-2026-10-07-P5：清空对话确认弹窗
        if (showClearConfirm) {
            AlertDialog(
                onDismissRequest = { showClearConfirm = false },
                shape = RoundedCornerShape(20.dp),
                title = { Text("清空对话", fontWeight = FontWeight.SemiBold) },
                text = { Text("确定清空当前对话吗？清空后本页消息不可恢复。") },
                confirmButton = {
                    TextButton(onClick = {
                        viewModel.clearConversation()
                        showClearConfirm = false
                    }) { Text("清空", color = Error) }
                },
                dismissButton = {
                    TextButton(onClick = { showClearConfirm = false }) { Text("取消") }
                }
            )
        }

        // AI-ASSISTANT-VOICE-001：聆听中弹窗——倒计时提示 + 实时识别文本
        if (voiceState.isListening) {
            AlertDialog(
                onDismissRequest = { voiceViewModel.stopListening() },
                shape = RoundedCornerShape(20.dp),
                title = { Text("语音输入", fontWeight = FontWeight.SemiBold) },
                text = {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp
                            )
                            Spacer(Modifier.width(10.dp))
                            Text(voiceState.message)
                        }
                        if (voiceState.partialText.isNotBlank()) {
                            Spacer(Modifier.height(12.dp))
                            Text(
                                voiceState.partialText,
                                color = OnSurfaceVariant,
                                fontSize = 14.sp
                            )
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = { voiceViewModel.stopListening() }) { Text("取消") }
                }
            )
        }
    }
}

/** 空态引导：列出高频问法，降低首次使用门槛。 */
@Composable
private fun AssistantEmptyHint() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text("你好，我是仓库 AI 助手 🤖", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
        Spacer(Modifier.height(6.dp))
        Text(
            "可以直接问我：",
            fontSize = 13.sp,
            color = OnSurfaceSecondary
        )
        Spacer(Modifier.height(12.dp))
        listOf(
            "A001 还有多少库存",
            "今天概况",
            "查 IN26050001",
            "低库存报告",
            "帮我巡检仓库"
        ).forEach { hint ->
            Surface(
                shape = RoundedCornerShape(18.dp),
                color = CardBackground,
                tonalElevation = 1.dp,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
            ) {
                Text(
                    hint,
                    modifier = Modifier
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                    fontSize = 14.sp,
                    color = Primary,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

/** 消息气泡：用户右侧主色，助手左侧白底；助手带卡片/动作展示。 */
@Composable
private fun AssistantMessageBubble(message: AssistantChatMessage) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (message.isUser) Alignment.End else Alignment.Start
    ) {
        Surface(
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (message.isUser) 16.dp else 4.dp,
                bottomEnd = if (message.isUser) 4.dp else 16.dp
            ),
            color = if (message.isUser) Primary else CardBackground,
            tonalElevation = if (message.isUser) 0.dp else 1.dp
        ) {
            Text(
                message.text,
                modifier = Modifier
                    .padding(horizontal = 14.dp, vertical = 10.dp)
                    .widthIn(max = 300.dp),
                fontSize = 14.sp,
                lineHeight = 20.sp,
                color = if (message.isUser) Color.White else OnSurface
            )
        }
        // 助手消息附带的结构化卡片（物料/单据）
        if (!message.isUser && message.cards.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            message.cards.take(4).forEach { card ->
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = CardBackground,
                    tonalElevation = 1.dp,
                    modifier = Modifier
                        .fillMaxWidth(0.92f)
                        .padding(vertical = 3.dp)
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            card.title ?: "",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        card.meta?.let {
                            Spacer(Modifier.height(3.dp))
                            Text(
                                it,
                                fontSize = 12.sp,
                                color = OnSurfaceSecondary,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
            }
        }
        // 建议动作（仅展示文本标签）
        if (!message.isUser && message.actions.isNotEmpty()) {
            Row(
                modifier = Modifier.padding(top = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                message.actions.take(3).forEach { action ->
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = PrimaryContainer
                    ) {
                        Text(
                            action.label ?: "",
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            fontSize = 12.sp,
                            color = Primary,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }
            }
        }
    }
}

/** 加载中气泡：静态省略号（三个点）。 */
@Composable
private fun AssistantTypingBubble() {
    Surface(
        shape = RoundedCornerShape(
            topStart = 4.dp,
            topEnd = 16.dp,
            bottomStart = 16.dp,
            bottomEnd = 16.dp
        ),
        color = CardBackground,
        tonalElevation = 1.dp
    ) {
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            repeat(3) {
                Box(
                    modifier = Modifier
                        .size(7.dp)
                        .clip(RoundedCornerShape(50))
                        .background(OnSurfaceSecondary.copy(alpha = 0.5f))
                )
            }
        }
    }
}
