package com.factory.wms.ui.components

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.navigation.NavHostController
import com.factory.wms.ui.navigation.Screen
import com.factory.wms.ui.theme.OnSurfaceVariant
import com.factory.wms.ui.theme.Primary
import com.factory.wms.ui.theme.PrimaryDark
import com.factory.wms.ui.viewmodel.auth.AuthViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceCommand
import com.factory.wms.ui.viewmodel.voice.VoiceCommandViewModel
import com.factory.wms.ui.viewmodel.voice.VoiceDraftStage
import com.factory.wms.ui.viewmodel.voice.VoiceOutDraftViewModel
import kotlinx.coroutines.launch

/**
 * 语音助手悬浮层：叠加在 NavHost 之上，仅登录态显示。
 * 提供悬浮麦克风按钮、聆听中弹窗、指令确认弹窗与错误提示。
 *
 * AI-VOICE-OUT-F01：新增**语音建单**通道。
 * 说「领8*25螺丝 1000个」时 [VoiceCommandViewModel] 会解析出
 * [VoiceCommand.CreateOutboundDraft]，此时不走"跳转出库页"，
 * 而是打开 [VoiceOutDraftDialog] 走"解析 → 消歧 → 确认 → 建草稿 → 跳转核对"流程。
 */
@Composable
fun VoiceAssistantOverlay(
    voiceViewModel: VoiceCommandViewModel,
    voiceDraftViewModel: VoiceOutDraftViewModel,
    authViewModel: AuthViewModel,
    navController: NavHostController,
    onDraftCreated: (orderNo: String, lines: List<Pair<String, Double>>) -> Unit = { _, _ -> }
) {
    val voiceState by voiceViewModel.uiState.collectAsState()
    val draftState by voiceDraftViewModel.uiState.collectAsState()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }
    var pendingCommand by remember { mutableStateOf<VoiceCommand?>(null) }
    val scope = rememberCoroutineScope()

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            voiceViewModel.startListening(context)
        } else {
            voiceViewModel.stopListening()
            voiceViewModel.clearResult()
            scope.launch { snackbarHostState.showSnackbar("需要麦克风权限才能使用语音指令") }
        }
    }

    // 收集识别出的指令，供确认弹窗展示
    LaunchedEffect(Unit) {
        voiceViewModel.commands.collect { command ->
            pendingCommand = command
        }
    }

    // 错误提示（识别失败/无权限/不支持）
    LaunchedEffect(voiceState.error) {
        voiceState.error?.let {
            snackbarHostState.showSnackbar(it)
            voiceViewModel.clearResult()
        }
    }

    // 建单错误提示（后端给出的具体原因，如"请填写数量"）
    LaunchedEffect(draftState.error) {
        draftState.error?.let { snackbarHostState.showSnackbar(it) }
    }

    // 草稿建成：通知上层做跳转（由 NavGraph 负责导航），并复位流程
    LaunchedEffect(draftState.stage) {
        if (draftState.stage == VoiceDraftStage.CREATED) {
            onDraftCreated(draftState.createdOrderNo, draftState.createdLines)
            voiceDraftViewModel.consumeCreated()
        }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 88.dp)
        )

        // 悬浮麦克风按钮
        FloatingActionButton(
            onClick = {
                val granted = ContextCompat.checkSelfPermission(
                    context, Manifest.permission.RECORD_AUDIO
                ) == PackageManager.PERMISSION_GRANTED
                if (granted) {
                    voiceViewModel.startListening(context)
                } else {
                    permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(20.dp),
            shape = RoundedCornerShape(16.dp),
            containerColor = Primary,
            contentColor = Color.White,
            elevation = FloatingActionButtonDefaults.elevation(6.dp)
        ) {
            if (voiceState.isListening) {
                CircularProgressIndicator(
                    modifier = Modifier.size(22.dp),
                    color = Color.White,
                    strokeWidth = 2.dp
                )
            } else {
                Icon(
                    Icons.Outlined.Mic,
                    contentDescription = "语音指令",
                    tint = Color.White
                )
            }
        }

        // 聆听中弹窗
        if (voiceState.isListening) {
            AlertDialog(
                onDismissRequest = { voiceViewModel.stopListening() },
                shape = RoundedCornerShape(20.dp),
                title = { Text("语音指令", fontWeight = FontWeight.SemiBold) },
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

        // 指令确认/未识别弹窗
        val pending = pendingCommand
        if (pending != null) {
            val draft = pending as? VoiceCommand.CreateOutboundDraft
            val unrecognized = pending is VoiceCommand.Unrecognized
            // AI-VOICE-OUT-F01：「领8*25螺丝 1000个」不弹"即将执行"确认框，
            // 直接进语音建单流程——用户要的是建单，不是跳转出库页。
            // 建单流程自身有核对弹窗（物料/数量/领料人），不会越过用户。
            if (draft != null) {
                LaunchedEffect(draft) {
                    pendingCommand = null
                    voiceDraftViewModel.loadWarehouses()
                    voiceDraftViewModel.parseAndMatch(draft.rawText)
                }
            } else {
                AlertDialog(
                    onDismissRequest = {
                        pendingCommand = null
                        voiceViewModel.clearResult()
                    },
                    shape = RoundedCornerShape(20.dp),
                    title = { Text("语音指令", fontWeight = FontWeight.SemiBold) },
                    text = {
                        Column {
                            if (voiceState.heardText.isNotBlank()) {
                                Text(
                                    "识别内容：${voiceState.heardText}",
                                    color = OnSurfaceVariant,
                                    fontSize = 14.sp
                                )
                                Spacer(Modifier.height(12.dp))
                            }
                            if (unrecognized) {
                                Text("未识别到可执行指令，可点「重试」重新说话。")
                            } else {
                                Text(
                                    "即将执行：${pending.label}",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 16.sp
                                )
                            }
                        }
                    },
                    confirmButton = {
                        if (unrecognized) {
                            TextButton(onClick = {
                                pendingCommand = null
                                voiceViewModel.clearResult()
                            }) { Text("关闭") }
                        } else {
                            TextButton(onClick = {
                                val cmd = pending
                                pendingCommand = null
                                voiceViewModel.clearResult()
                                executeVoiceCommand(cmd, navController, authViewModel)
                            }) {
                                Text("执行", color = PrimaryDark, fontWeight = FontWeight.SemiBold)
                            }
                        }
                    },
                    dismissButton = {
                        TextButton(onClick = {
                            pendingCommand = null
                            voiceViewModel.clearResult()
                            voiceViewModel.startListening(context)
                        }) { Text("重试") }
                    }
                )
            }
        }

        // 语音建单流程弹窗（解析/选择/确认/未找到）
        VoiceOutDraftDialog(
            state = draftState,
            onChooseMaterial = { voiceDraftViewModel.chooseMaterial(it) },
            onQuantityChange = { voiceDraftViewModel.onQuantityChange(it) },
            onPickerChange = { voiceDraftViewModel.onPickerChange(it) },
            onConfirm = { voiceDraftViewModel.createDraft() },
            onBackToChoice = { voiceDraftViewModel.backToChoice() },
            onDismiss = {
                voiceDraftViewModel.clearError()
                voiceDraftViewModel.reset()
            },
            onRetry = {
                voiceDraftViewModel.reset()
                voiceViewModel.startListening(context)
            }
        )
    }
}

private fun executeVoiceCommand(
    command: VoiceCommand,
    navController: NavHostController,
    authViewModel: AuthViewModel
) {
    when (command) {
        is VoiceCommand.Navigate -> navController.navigate(command.screen.route) {
            launchSingleTop = true
        }
        VoiceCommand.GoBack -> navController.popBackStack()
        VoiceCommand.GoHome -> navController.navigate(Screen.Home.route) {
            popUpTo(0) { inclusive = true }
            launchSingleTop = true
        }
        VoiceCommand.Logout -> {
            authViewModel.logout()
            navController.navigate(Screen.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
        // 建单指令由 VoiceAssistantOverlay 内部的 LaunchedEffect 消费，
        // 不会走到这里（且建单流程自带核对弹窗，无需二次确认）。
        is VoiceCommand.CreateOutboundDraft -> Unit
        VoiceCommand.Unrecognized -> Unit
    }
}