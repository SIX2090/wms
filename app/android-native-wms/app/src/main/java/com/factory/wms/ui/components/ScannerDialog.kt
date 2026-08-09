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

@Composable
fun ScannerDialog(
    onDismiss: () -> Unit,
    onBarcodeScanned: (String) -> Unit
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
                                            @OptIn(ExperimentalGetImage::class)
                                            val mediaImage = imageProxy.image
                                            if (mediaImage != null) {
                                                val image = InputImage.fromMediaImage(
                                                    mediaImage,
                                                    imageProxy.imageInfo.rotationDegrees
                                                )
                                                // Only the first match is delivered; the flag prevents
                                                // duplicate callbacks while the dialog is closing (H4).
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
                                    @androidx.annotation.OptIn(androidx.camera.camera2.interop.ExperimentalCamera2Interop::class)
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
                    "将条码置于框内扫描",
                    color = Color.White,
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

            // Bottom hint
            Text(
                "将条码对准扫描框，自动识别",
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 60.dp),
                color = Color.White.copy(alpha = 0.7f),
                fontSize = 14.sp,
                textAlign = TextAlign.Center
            )
        }
    }
}