package com.factory.wms.ui.components

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * AI-MOB-CONTINUOUS-SCAN-01：连续扫描的节流窗口（毫秒）。
 *
 * 为什么要节流：弹窗不再随扫码关闭后，同一件货停在镜头前会被相机连续多帧命中。
 * 900ms 的窗口既覆盖"同一码在 1~3 帧内反复命中"（30fps 下约 33~100ms），
 * 又不拖慢人手换件的节奏（实测间隔通常 > 1s）。
 */
private const val CONTINUOUS_SCAN_THROTTLE_MS = 900L

@androidx.annotation.OptIn(
    markerClass = [
        ExperimentalGetImage::class,
        androidx.camera.camera2.interop.ExperimentalCamera2Interop::class
    ]
)
@Composable
fun ScannerDialog(
    onDismiss: () -> Unit,
    onBarcodeScanned: (String) -> Unit,
    /**
     * 连续扫描模式（AI-MOB-CONTINUOUS-SCAN-01）。
     *
     * 开启后扫中一码**不关闭**对话框，相机保持预览，用户可以接着扫下一件。
     * 仓库现场一个托盘常 20~50 件货，旧行为"扫一码关一次相机 + 手动再点开"
     * 会让一次收货多出 40~100 次点击，是移动端最大的一处效率损耗。
     *
     * 关闭时保持旧行为（扫中即回调并退出），供"只需扫一个码"的场景使用。
     */
    continuous: Boolean = true,
    /** 连续模式下已扫条数，用于顶部计数回显（由调用方维护，弹窗不自己计数）。 */
    scannedCount: Int = 0,
    /** 连续模式下最近一次扫中的条码，用于顶部回显"已加 XXX"。 */
    lastScannedCode: String? = null,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasCameraPermission by remember { mutableStateOf(false) }
    var isTorchOn by remember { mutableStateOf(false) }
    var cameraError by remember { mutableStateOf<String?>(null) }

    // Track the camera provider and preview view for cleanup
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    var cameraProvider by remember { mutableStateOf<ProcessCameraProvider?>(null) }
    // Camera object returned by bindToLifecycle, used to control the torch (C1)
    var camera by remember { mutableStateOf<Camera?>(null) }

    // Reuse the ML Kit scanner and the analysis executor across fibre creations (H2/C2).
    // They are created once and explicitly shut down on dispose to avoid leaks.
    val barcodeScanner = remember {
        BarcodeScanning.getClient(
            BarcodeScannerOptions.Builder()
                .setBarcodeFormats(Barcode.FORMAT_ALL_FORMATS)
                .build()
        )
    }
    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    // Thread-safe guard so the scanf callback fires only once per dialog open (H4)
    val scannedFlag = remember { AtomicBoolean(false) }

    // AI-MOB-CONTINUOUS-SCAN-01：连续模式下 scannedFlag 不再"一置位到底"，
    // 而是每次回调后延迟复位，形成节流窗口：
    //   - 挡住同一件货在镜头前停留时被重复回调（原先靠"关弹窗"达到同样效果，现在弹窗不关）；
    //   - 窗口过后自动放行，下一条码立即可扫。
    // 节流窗口取 900ms：实测人手换件的间隔通常 > 1s，而相机在 30fps 下
    // 同一码会在 1~3 帧内被反复命中，900ms 足以覆盖两条极端情况且不拖慢节奏。
    val continuousRef = rememberUpdatedState(continuous)

    // 节流窗口用"令牌"实现，避免 postDelayed 与手动放行（继续扫按钮）互相踩：
    //   - requestId 每开一个新窗口就自增；定时复位只在"自己仍是当前窗口"时生效。
    //   - 若用户点了"继续扫"（手动开新窗口），先前排队的定时复位会发现 requestId
    //     已经变了，于是直接放弃 —— 否则它会把用户刚扫中的码错误放行出去。
    val throttleOwner = remember {
        object {
            val handler = android.os.Handler(android.os.Looper.getMainLooper())
            var requestId = 0

            /** 开一个节流窗口：窗口结束后自动复位 scannedFlag。 */
            fun arm() {
                requestId++
                val mine = requestId
                handler.postDelayed({
                    if (requestId == mine) scannedFlag.set(false)
                }, CONTINUOUS_SCAN_THROTTLE_MS)
            }

            /** 立即复位并接管为当前窗口（用户在窗口期内又扫了一件）。 */
            fun releaseNow() {
                requestId++
                scannedFlag.set(false)
            }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
        if (!granted) {
            Toast.makeText(context, "需要相机权限才能扫码", Toast.LENGTH_SHORT).show()
            onDismiss()
        }
    }

    LaunchedEffect(Unit) {
        when {
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED -> hasCameraPermission = true
            else -> permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    // Release all camera resources and the executor/scanner when the dialog is dismissed (C2/H2)
    DisposableEffect(Unit) {
        onDispose {
            cameraProvider?.unbindAll()
            analysisExecutor.shutdown()
            barcodeScanner.close()
            camera = null
            previewView = null
            cameraProvider = null
        }
    }

    // Scanning animation
    val infiniteTransition = rememberInfiniteTransition(label = "scan_line")
    val scanLineOffset by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "scan_line_offset"
    )

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            if (hasCameraPermission && cameraError == null) {
                AndroidView(
                    factory = { ctx ->
                        val view = PreviewView(ctx).apply {
                            scaleType = PreviewView.ScaleType.FIT_CENTER
                        }
                        previewView = view

                        // Initialize camera asynchronously using addListener (non-blocking)
                        val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                        cameraProviderFuture.addListener({
                            try {
                                val provider = cameraProviderFuture.get()
                                cameraProvider = provider

                                val preview = Preview.Builder().build().also {
                                    it.setSurfaceProvider(view.surfaceProvider)
                                }

                                // BUG-2026-08-09-002: 旧写法同时调用 setTargetAspectRatio + setTargetResolution，
                                // CameraX 1.3+ 抛 IllegalArgumentException，相机直接绑不上 → "摄像头不可用"。
                                // 改用官方推荐的 ResolutionSelector：16:9 比例 + 最高可用分辨率，
                                // 国产机多摄/不同分辨率自动适配，避免崩溃。
                                val resolutionSelector = ResolutionSelector.Builder()
                                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY)
                                    .setResolutionStrategy(ResolutionStrategy.HIGHEST_AVAILABLE_STRATEGY)
                                    .build()

                                val imageAnalysis = ImageAnalysis.Builder()
                                    .setResolutionSelector(resolutionSelector)
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                                    .build()
                                    .also {
                                        it.setAnalyzer(analysisExecutor) { imageProxy: ImageProxy ->
                                            val mediaImage = imageProxy.image
                                            if (mediaImage != null) {
                                                val image = InputImage.fromMediaImage(
                                                    mediaImage,
                                                    imageProxy.imageInfo.rotationDegrees
                                                )
                                                // scannedFlag 语义（H4 + AI-MOB-CONTINUOUS-SCAN-01）：
                                                //   - 非连续模式：置位即代表"本次弹窗已交付结果"，回调后由调用方
                                                //     关闭弹窗，与旧行为一致（H4 原意）。
                                                //   - 连续模式：置位只是"当前节流窗口内"，由 releaseFlag
                                                //     在 900ms 后复位，故弹窗可一直扫下去。
                                                // 两种情况都保留了"同一帧/同一件货不重复回调"的保护。
                                                if (scannedFlag.get()) {
                                                    imageProxy.close()
                                                } else {
                                                    barcodeScanner.process(image)
                                                        .addOnSuccessListener { barcodes ->
                                                            // BUG-2026-08-09-001: 只在真正解码出条码时才置位 scannedFlag。
                                                            // ML Kit 对未识别到条码的帧同样回调成功（barcodes 为空）；
                                                            // 若无条件置位，相机首帧（几乎必为空结果）会永久关闭
                                                            // 后续所有帧的分析，表现为"扫码无法识别条码"。
                                                            for (barcode in barcodes) {
                                                                val rawValue = barcode.rawValue
                                                                if (!rawValue.isNullOrEmpty() && scannedFlag.compareAndSet(false, true)) {
                                                                    onBarcodeScanned(rawValue)
                                                                    // 连续模式：交付后重新武装节流窗口，让下一条码能进来；
                                                                    // 非连续模式：保持置位，等调用方关闭弹窗（旧行为）。
                                                                    if (continuousRef.value) {
                                                                        throttleOwner.arm()
                                                                    }
                                                                    return@addOnSuccessListener
                                                                }
                                                            }
                                                        }
                                                        .addOnFailureListener { e ->
                                                            android.util.Log.w("ScannerDialog", "条码识别失败，继续分析后续帧", e)
                                                        }
                                                        .addOnCompleteListener {
                                                            // Close exactly once, here, after success/failure
                                                            imageProxy.close()
                                                        }
                                                }
                                            } else {
                                                imageProxy.close()
                                            }
                                        }
                                    }

                                val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

                                provider.unbindAll()
                                camera = provider.bindToLifecycle(
                                    lifecycleOwner,
                                    cameraSelector,
                                    preview,
                                    imageAnalysis
                                )

                                // Enable continuous autofocus for reliable barcode scanning
                                camera?.let { cam ->
                                    val camera2Control = androidx.camera.camera2.interop.Camera2CameraControl.from(cam.cameraControl)
                                    val options = androidx.camera.camera2.interop.CaptureRequestOptions.Builder()
                                        .setCaptureRequestOption(
                                            android.hardware.camera2.CaptureRequest.CONTROL_AF_MODE,
                                            android.hardware.camera2.CameraMetadata.CONTROL_AF_MODE_CONTINUOUS_PICTURE
                                        )
                                        .build()
                                    camera2Control.captureRequestOptions = options
                                }
                            } catch (e: Exception) {
                                cameraError = e.message ?: "相机启动失败"
                                Toast.makeText(ctx, cameraError, Toast.LENGTH_SHORT).show()
                            }
                        }, ContextCompat.getMainExecutor(ctx))

                        view
                    },
                    modifier = Modifier.fillMaxSize()
                )

                // Fullscreen scan frame: the whole preview is the scan area.
                // No dark mask is applied so barcodes can be recognized anywhere on screen.
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val scanBoxWidth = size.width
                    val scanBoxHeight = size.height
                    val scanBoxLeft = 0f
                    val scanBoxTop = 0f

                    val cornerLength = 48f
                    val strokeWidth = 5f
                    val cornerColor = Color(0xFF4361EE)
                    val inset = 24f

                    // Corner markers stay near the screen edges to delimit the fullscreen frame
                    val left = scanBoxLeft + inset
                    val top = scanBoxTop + inset
                    val right = scanBoxLeft + scanBoxWidth - inset
                    val bottom = scanBoxTop + scanBoxHeight - inset

                    drawLine(cornerColor, Offset(left, top + cornerLength), Offset(left, top), strokeWidth)
                    drawLine(cornerColor, Offset(left, top), Offset(left + cornerLength, top), strokeWidth)

                    drawLine(cornerColor, Offset(right - cornerLength, top), Offset(right, top), strokeWidth)
                    drawLine(cornerColor, Offset(right, top), Offset(right, top + cornerLength), strokeWidth)

                    drawLine(cornerColor, Offset(left, bottom - cornerLength), Offset(left, bottom), strokeWidth)
                    drawLine(cornerColor, Offset(left, bottom), Offset(left + cornerLength, bottom), strokeWidth)

                    drawLine(cornerColor, Offset(right - cornerLength, bottom), Offset(right, bottom), strokeWidth)
                    drawLine(cornerColor, Offset(right, bottom), Offset(right, bottom - cornerLength), strokeWidth)

                    val lineY = top + (bottom - top - 4f) * scanLineOffset
                    drawLine(
                        color = Color(0xFF4361EE).copy(alpha = 0.8f),
                        start = Offset(left + 8f, lineY),
                        end = Offset(right - 8f, lineY),
                        strokeWidth = 2f
                    )
                }
            } else if (cameraError != null) {
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        "摄像头不可用",
                        color = Color.White,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        cameraError ?: "未知错误",
                        color = Color.White.copy(alpha = 0.7f),
                        fontSize = 14.sp,
                        textAlign = TextAlign.Center
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        "请手动输入物料编码",
                        color = Color.White.copy(alpha = 0.5f),
                        fontSize = 13.sp
                    )
                }
            }

            // Top bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 48.dp)
                    .statusBarsPadding(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier
                        .size(44.dp)
                        .background(
                            Color.White.copy(alpha = 0.15f),
                            RoundedCornerShape(12.dp)
                        )
                ) {
                    Icon(
                        Icons.Filled.Close,
                        "关闭",
                        tint = Color.White,
                        modifier = Modifier.size(22.dp)
                    )
                }

                Text(
                    if (continuous && scannedCount > 0) "已扫 $scannedCount 件 · 继续扫下一件"
                    else "将条码置于框内扫描",
                    color = if (continuous && scannedCount > 0) Color(0xFF7CFFB2) else Color.White,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium
                )

                // Torch toggle actually drives CameraControl.enableTorch (C1)
                IconButton(
                    onClick = {
                        val cam = camera
                        if (cam != null && cam.cameraInfo.hasFlashUnit()) {
                            val newValue = !isTorchOn
                            cam.cameraControl.enableTorch(newValue)
                            isTorchOn = newValue
                        }
                    },
                    modifier = Modifier
                        .size(44.dp)
                        .background(
                            Color.White.copy(alpha = 0.15f),
                            RoundedCornerShape(12.dp)
                        )
                ) {
                    Icon(
                        if (isTorchOn) Icons.Filled.FlashOn else Icons.Filled.FlashOff,
                        if (isTorchOn) "关闭手电筒" else "打开手电筒",
                        tint = if (isTorchOn) Color(0xFFFFD700) else Color.White,
                        modifier = Modifier.size(22.dp)
                    )
                }
            }

            // Bottom hint / 连续扫描反馈区（AI-MOB-CONTINUOUS-SCAN-01）
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp)
                    .padding(bottom = 48.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                if (continuous && lastScannedCode != null) {
                    // 回显"刚扫到了什么"——连续模式下弹窗不关，用户需要确认这一件确实进去了，
                    // 否则会怀疑漏扫而重复扫（重复扫会被 addScanLine 累加，反而多货）。
                    Surface(
                        color = Color(0xFF1B5E20).copy(alpha = 0.92f),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text(
                            "已加入：$lastScannedCode",
                            color = Color.White,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(14.dp))
                }

                Text(
                    if (continuous) "连续扫描中 · 可连续扫多件" else "将条码对准扫描框，自动识别",
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 14.sp,
                    textAlign = TextAlign.Center
                )

                if (continuous) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        // 手速快于节流窗口时不用干等，点一下立即放行
                        OutlinedButton(
                            onClick = { throttleOwner.releaseNow() },
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = Color.White
                            )
                        ) {
                            Text("继续扫", fontSize = 15.sp)
                        }
                        Button(
                            onClick = onDismiss,
                            modifier = Modifier
                                .weight(1f)
                                .height(48.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF4361EE)
                            )
                        ) {
                            Text(
                                if (scannedCount > 0) "完成（$scannedCount）" else "完成",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    }
                }
            }
        }
    }
}