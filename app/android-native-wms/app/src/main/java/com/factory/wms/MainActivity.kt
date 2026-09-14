package com.factory.wms

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.factory.wms.ui.navigation.AppNavGraph
import com.factory.wms.ui.theme.WmsTheme
import java.io.File

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // BUG-2026-09-13-023（第二轮，权限线路）：**绝不能在 onCreate 中申请权限**。
        //
        // 现场截图：`WMS扫码屡次停止运行` 与系统「是否允许访问相机？1/2」弹框同屏出现，
        // 说明崩溃的触发点就是权限弹框本身。
        //
        // 根因：`requestPermissions()` 是**同步打断式**调用——它会让 Activity 立即进入
        // PAUSED 去显示系统弹框。此前调用位置在 `setContent{}` **之前**，意味着
        // 弹框弹出时 `setContent` 尚未执行、Compose 的 View 树尚未建立；用户点击
        // 允许/拒绝后 Activity 恢复，回调与后续组合撞在未初始化的宿主上 → 进程被杀。
        //
        // 历史教训：MOBILE-PERMISSION-001 共 5 次提交（90a0ef9 / ad39926 / b9516a9 /
        // e950815）都在反复更换「用什么 API 申请」，从未质疑「在 onCreate 里、setContent
        // 之前申请」这个位置本身，因此 5 次全部无效（台账已记「无法取得设备 logcat」，
        // 属盲改）。e950815 还把 onRequestPermissionsResult 一并删除，回调无人处理。
        //
        // 正确做法：权限一律**按需、在 Compose 内申请**——两个权限都已具备该机制，
        // 启动期申请纯属冗余：
        //   - CAMERA      → ui/components/ScannerDialog.kt（rememberLauncherForActivityResult
        //                   + LaunchedEffect，进入扫码弹窗时才请求）
        //   - RECORD_AUDIO → ui/components/VoiceAssistant.kt（同上，启用语音时才请求）
        // 因此此处**不再做任何启动期权限申请**，直接组合 UI。

        setContent {
            WmsTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    // BUG-2026-09-14-028（第三根因攻坚，诊断桩，非业务改动）：
                    // 3.8.1 仍冷启动闪退，说明真实根因从未被捕获（历轮修复均无 logcat）。
                    // WmsApplication 的崩溃日志器已把堆栈写入 filesDir/crash/last_crash.txt，
                    // 但 release 包在非 root 手机上无法用 adb 读取该文件。
                    // 因此：若检测到上次崩溃的堆栈文件，先渲染本报告页（**不加载会崩的
                    // AppNavGraph**），让用户截图/复制后发回，定位真凶后再修——不再盲改。
                    var pendingCrash by remember { mutableStateOf(readPendingCrash()) }
                    val crash = pendingCrash
                    if (crash != null) {
                        CrashReportScreen(crashText = crash, onDismiss = {
                            clearPendingCrash()
                            pendingCrash = null
                        })
                    } else {
                        AppNavGraph()
                    }
                }
            }
        }
    }

    /** 读取上次崩溃写入的堆栈；不存在或读取失败返回 null（按无崩溃处理）。 */
    private fun readPendingCrash(): String? = runCatching {
        val f = File(filesDir, "crash/last_crash.txt")
        if (f.exists()) f.readText() else null
    }.getOrNull()

    /** 用户确认已记录后删除崩溃文件，下次正常进入主界面。 */
    private fun clearPendingCrash() {
        runCatching { File(filesDir, "crash/last_crash.txt").delete() }
    }
}

/**
 * 崩溃报告页：把上次崩溃的堆栈直接展示给用户，供截图/复制回传。
 *
 * 刻意做成**极简、零依赖**的静态页：不创建任何 ViewModel、不触网、不读数据库，
 * 因此即使主界面（AppNavGraph 组合期）必崩，本页也能稳定渲染——这是"崩溃后还能
 * 打开看到错误"的关键。崩溃堆栈里带有 version=3.8.x (versionCode)，可核对版本。
 */
@Composable
private fun CrashReportScreen(crashText: String, onDismiss: () -> Unit) {
    val clipboard = LocalClipboardManager.current
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "应用上次异常退出",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.error
        )
        Spacer(Modifier.height(8.dp))
        Text(
            text = "请把下面内容「截图」发给技术人员，或点「复制崩溃信息」后粘贴到微信发送。这能帮助一次定位问题，避免反复返工：",
            style = MaterialTheme.typography.bodyMedium
        )
        Spacer(Modifier.height(12.dp))
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .verticalScroll(rememberScrollState())
                .padding(8.dp)
        ) {
            Text(text = crashText, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(12.dp))
        Row {
            Button(onClick = { clipboard.setText(AnnotatedString(crashText)) }) {
                Text("复制崩溃信息")
            }
            Spacer(Modifier.width(12.dp))
            OutlinedButton(onClick = onDismiss) {
                Text("我已记录，继续使用")
            }
        }
    }
}
