package com.factory.wms

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.factory.wms.ui.navigation.AppNavGraph
import com.factory.wms.ui.theme.WmsTheme

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
                    AppNavGraph()
                }
            }
        }
    }
}
