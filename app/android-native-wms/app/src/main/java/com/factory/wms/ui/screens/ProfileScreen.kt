package com.factory.wms.ui.screens

import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.background
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.factory.wms.BuildConfig
import com.factory.wms.ui.components.StatusBarIconEffect
import com.factory.wms.ui.theme.*
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.util.ScanFeedback
import com.factory.wms.WmsApplication
import com.factory.wms.update.AppUpdatePanel
import kotlinx.coroutines.launch

/** "我的"页：账号信息、服务器信息、语音指令说明、退出登录。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    authViewModel: AuthViewModel,
    onLogout: () -> Unit
) {
    val uiState by authViewModel.uiState.collectAsState()
    var showLogoutDialog by remember { mutableStateOf(false) }
    // AI-MOB-SCAN-UX-01：扫码声音/震动反馈开关。
    // 初值取 ScanFeedback 的内存缓存（进程启动时已 warmUp），避免首帧闪烁成默认值。
    val context = LocalContext.current
    val appUpdates = remember(context) {
        runCatching { (context.applicationContext as? WmsApplication)?.appUpdates }.getOrNull()
    }
    var scanSoundEnabled by remember { mutableStateOf(ScanFeedback.soundEnabled) }
    var scanVibrationEnabled by remember { mutableStateOf(ScanFeedback.vibrationEnabled) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        containerColor = Background
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
        ) {
            // ── Header ──
            // Scaffold 已预留状态栏安全区，图标颜色跟随实际背景明暗。
            StatusBarIconEffect(darkIcons = !isSystemInDarkTheme())
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(Primary, PrimaryDark)
                        )
                    )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // 头像（白色描边圆环 + 首字母）
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = 0.12f))
                            .padding(4.dp)
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = 0.2f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            uiState.username.take(1).uppercase(),
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 24.sp
                        )
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        // 长用户名按可用宽度换行，避免截断或挤压退出区域。
                        Text(
                            uiState.username.ifBlank { "未登录" },
                            color = Color.White,
                            fontWeight = FontWeight.Bold,
                            fontSize = 20.sp,
                            softWrap = true
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = Color.White.copy(alpha = 0.16f)
                        ) {
                            Text(
                                "角色 · ${uiState.role.ifBlank { "操作员" }}",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 3.dp),
                                color = Color.White.copy(alpha = 0.9f),
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // ── 服务器信息 ──
            ProfileSectionCard("服务器信息") {
                Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp)) {
                    SelectionContainer(Modifier.fillMaxWidth()) {
                        Text(uiState.baseUrl, modifier = Modifier.fillMaxWidth(),
                            style = MaterialTheme.typography.bodyMedium, softWrap = true)
                    }
                    TextButton(onClick = {
                        val copied = runCatching {
                            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                            clipboard.setPrimaryClip(ClipData.newPlainText("服务器地址", uiState.baseUrl))
                        }.isSuccess
                        scope.launch { snackbar.showSnackbar(if (copied) "服务器地址已复制" else "复制失败，请长按地址复制") }
                    }, enabled = uiState.baseUrl.isNotBlank(),
                        modifier = Modifier.align(Alignment.End).heightIn(min = 48.dp)) {
                        Icon(Icons.Outlined.ContentCopy, contentDescription = null)
                        Spacer(Modifier.width(4.dp)); Text("复制")
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // ── 扫码设置（AI-MOB-SCAN-UX-01）──
            ProfileSectionCard("扫码设置") {
                Text("用于连续扫码时的操作反馈", modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    style = MaterialTheme.typography.bodyMedium, color = OnSurfaceVariant)
                ProfileToggleRow(icon = Icons.Outlined.VolumeUp, label = "扫码提示音",
                    description = "区分成功与失败", checked = scanSoundEnabled,
                    onCheckedChange = { value -> scanSoundEnabled = value; ScanFeedback.setSoundEnabled(context, value) })
                ProfileToggleRow(icon = Icons.Outlined.Vibration, label = "扫码震动",
                    description = "区分成功与失败", checked = scanVibrationEnabled,
                    onCheckedChange = { value -> scanVibrationEnabled = value; ScanFeedback.setVibrationEnabled(context, value) },
                    showDivider = false)
            }

            Spacer(modifier = Modifier.height(12.dp))

            // ── 应用信息 ──
            ProfileSectionCard("应用信息") {
                ProfileRow(
                    icon = Icons.Outlined.Info,
                    label = "版本",
                    value = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                    showDivider = false
                )
                appUpdates?.let { AppUpdatePanel(it) }
            }

            if (BuildConfig.VOICE_UI_ENABLED) {
                Spacer(modifier = Modifier.height(12.dp))

                // ── 语音指令说明 ──
                ProfileSectionCard("语音指令说明") {
                    ProfileRow(
                        icon = Icons.Outlined.ArrowDownward,
                        label = "去入库",
                        value = "说“入库”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.ArrowUpward,
                        label = "去出库",
                        value = "说“出库”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.Search,
                        label = "去查库存",
                        value = "说“查库存”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.Inventory2,
                        label = "去盘点",
                        value = "说“盘点”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.Description,
                        label = "识别单据",
                        value = "说“识别单据”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.ArrowBack,
                        label = "返回上一页",
                        value = "说“返回”",
                        isHint = true
                    )
                    ProfileRow(
                        icon = Icons.Outlined.Home,
                        label = "回到首页",
                        value = "说“回到首页”",
                        isHint = true
                    )
                    ProfileRow(
                        // AI-ASSISTANT-MOBILE-001：语音也支持任意 AI 问答（经 LLM 意图路由）
                        icon = Icons.Outlined.SmartToy,
                        label = "AI 问答",
                        value = "说任意问题，如“低库存报告”",
                        isHint = true,
                        showDivider = false
                    )
                }

            }

            Spacer(modifier = Modifier.height(24.dp))

            // ── 退出登录（白底红字卡片，比纯红按钮更克制精致） ──
            Card(
                onClick = { showLogoutDialog = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = CardBackground),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 16.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Outlined.Logout,
                        null,
                        tint = Error,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "退出登录",
                        color = Error,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 16.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }

    if (showLogoutDialog) {
        AlertDialog(
            onDismissRequest = { showLogoutDialog = false },
            shape = RoundedCornerShape(20.dp),
            title = { Text("退出登录", fontWeight = FontWeight.SemiBold) },
            text = { Text("确定要退出当前账号吗？") },
            confirmButton = {
                TextButton(onClick = {
                    showLogoutDialog = false
                    authViewModel.logout()
                    onLogout()
                }) {
                    Text("确定退出", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showLogoutDialog = false }) {
                    Text("取消")
                }
            }
        )
    }
}

@Composable
private fun ProfileSectionCard(
    title: String,
    content: @Composable () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(vertical = 6.dp)) {
            Text(
                title,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            content()
        }
    }
}

@Composable
private fun ProfileToggleRow(
    icon: ImageVector,
    label: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    showDivider: Boolean = true
) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .toggleable(value = checked, role = Role.Switch, onValueChange = onCheckedChange)
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(SurfaceVariant),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, null, tint = OnSurfaceVariant, modifier = Modifier.size(18.dp))
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    label,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                // 副标题说明"开了会怎样"——只有开关没有说明，用户不敢乱动
                Text(
                    description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            Switch(checked = checked, onCheckedChange = null)
        }
        if (showDivider) {
            HorizontalDivider(
                modifier = Modifier.padding(start = 64.dp, end = 16.dp),
                color = DividerSoft,
                thickness = 1.dp
            )
        }
    }
}

@Composable
private fun ProfileRow(
    icon: ImageVector,
    label: String,
    value: String,
    isHint: Boolean = false,
    showDivider: Boolean = true
) {
    Column {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(if (isHint) PrimaryContainer else SurfaceVariant),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                icon,
                null,
                tint = if (isHint) Primary else OnSurfaceVariant,
                modifier = Modifier.size(18.dp)
            )
        }
        Spacer(modifier = Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                label,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
        // AI-APP-FIX-204：删除 ChevronRight 假箭头——本页所有 ProfileRow 均不可点，
        // 箭头暗示"点进去有详情"，点了没反应属于误导。
        // 长值在自有空间换行，保持完整并避免挤压标签。
        Text(
            value,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
            color = if (isHint) Primary else MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.End,
            softWrap = true
        )
    }
    if (showDivider) {
        HorizontalDivider(
            modifier = Modifier.padding(start = 64.dp, end = 16.dp),
            color = DividerSoft,
            thickness = 1.dp
        )
    }
    }
}
