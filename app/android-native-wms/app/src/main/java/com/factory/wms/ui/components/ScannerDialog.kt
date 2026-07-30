package com.factory.wms.ui.components

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

@Composable
fun ScannerDialog(
    onDismiss: () -> Unit,
    onBarcodeScanned: (String) -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasCameraPermission by remember { mutableStateOf(false) }
    var isTorchOn by remember { mutableStateOf(false) }

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
        properties = androidx.compose.ui.window.DialogProperties(
            usePlatformDefaultWidth = false,
            decorFitsSystemWindows = false
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black)
        ) {
            if (hasCameraPermission) {
                // Camera preview
                AndroidView(
                    factory = { ctx ->
                        val previewView = PreviewView(ctx)
                        val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)

                        cameraProviderFuture.addListener({
                            val cameraProvider = cameraProviderFuture.get()
                            val preview = Preview.Builder().build().also {
                                it.setSurfaceProvider(previewView.surfaceProvider)
                            }

                            // Image analysis for barcode scanning
                            val options = BarcodeScannerOptions.Builder()
                                .setBarcodeFormats(
                                    Barcode.FORMAT_ALL_FORMATS
                                )
                                .build()
                            val scanner = BarcodeScanning.getClient(options)

                            val analysisExecutor = Executors.newSingleThreadExecutor()
                            val imageAnalysis = ImageAnalysis.Builder()
                                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                .build()
                                .also {
                                    it.setAnalyzer(analysisExecutor) { imageProxy: ImageProxy ->
                                        @androidx.camera.core.ExperimentalGetImage
                                        val mediaImage = imageProxy.image
                                        if (mediaImage != null) {
                                            val image = InputImage.fromMediaImage(
                                                mediaImage,
                                                imageProxy.imageInfo.rotationDegrees
                                            )
                                            scanner.process(image)
                                                .addOnSuccessListener { barcodes ->
                                                    for (barcode in barcodes) {
                                                        barcode.rawValue?.let { rawValue ->
                                                            imageProxy.close()
                                                            onBarcodeScanned(rawValue)
                                                            return@addOnSuccessListener
                                                        }
                                                    }
                                                }
                                                .addOnCompleteListener {
                                                    imageProxy.close()
                                                }
                                        } else {
                                            imageProxy.close()
                                        }
                                    }
                                }

                            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

                            try {
                                cameraProvider.unbindAll()
                                cameraProvider.bindToLifecycle(
                                    lifecycleOwner,
                                    cameraSelector,
                                    preview,
                                    imageAnalysis
                                )
                            } catch (_: Exception) {
                                Toast.makeText(ctx, "相机启动失败", Toast.LENGTH_SHORT).show()
                            }
                        }, ContextCompat.getMainExecutor(ctx))

                        previewView
                    },
                    modifier = Modifier.fillMaxSize()
                )

                // Dark overlay with cutout
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val scanBoxWidth = size.width * 0.7f
                    val scanBoxHeight = scanBoxWidth * 0.6f
                    val scanBoxLeft = (size.width - scanBoxWidth) / 2f
                    val scanBoxTop = (size.height - scanBoxHeight) / 2f

                    // Dark overlay
                    drawRect(
                        color = Color.Black.copy(alpha = 0.5f),
                        size = size
                    )

                    // Cutout
                    drawRoundRect(
                        color = Color.Transparent,
                        topLeft = Offset(scanBoxLeft, scanBoxTop),
                        size = Size(scanBoxWidth, scanBoxHeight),
                        cornerRadius = CornerRadius(16f, 16f),
                        blendMode = BlendMode.Clear
                    )

                    // Scan box border
                    val cornerLength = 40f
                    val strokeWidth = 4f
                    val cornerColor = Color(0xFF4361EE)

                    // Top-left corner
                    drawLine(cornerColor, Offset(scanBoxLeft, scanBoxTop + cornerLength), Offset(scanBoxLeft, scanBoxTop), strokeWidth)
                    drawLine(cornerColor, Offset(scanBoxLeft, scanBoxTop), Offset(scanBoxLeft + cornerLength, scanBoxTop), strokeWidth)

                    // Top-right corner
                    drawLine(cornerColor, Offset(scanBoxLeft + scanBoxWidth - cornerLength, scanBoxTop), Offset(scanBoxLeft + scanBoxWidth, scanBoxTop), strokeWidth)
                    drawLine(cornerColor, Offset(scanBoxLeft + scanBoxWidth, scanBoxTop), Offset(scanBoxLeft + scanBoxWidth, scanBoxTop + cornerLength), strokeWidth)

                    // Bottom-left corner
                    drawLine(cornerColor, Offset(scanBoxLeft, scanBoxTop + scanBoxHeight - cornerLength), Offset(scanBoxLeft, scanBoxTop + scanBoxHeight), strokeWidth)
                    drawLine(cornerColor, Offset(scanBoxLeft, scanBoxTop + scanBoxHeight), Offset(scanBoxLeft + cornerLength, scanBoxTop + scanBoxHeight), strokeWidth)

                    // Bottom-right corner
                    drawLine(cornerColor, Offset(scanBoxLeft + scanBoxWidth - cornerLength, scanBoxTop + scanBoxHeight), Offset(scanBoxLeft + scanBoxWidth, scanBoxTop + scanBoxHeight), strokeWidth)
                    drawLine(cornerColor, Offset(scanBoxLeft + scanBoxWidth, scanBoxTop + scanBoxHeight), Offset(scanBoxLeft + scanBoxWidth, scanBoxTop + scanBoxHeight - cornerLength), strokeWidth)

                    // Scanning line
                    val lineY = scanBoxTop + (scanBoxHeight - 4f) * scanLineOffset
                    drawLine(
                        color = Color(0xFF4361EE).copy(alpha = 0.8f),
                        start = Offset(scanBoxLeft + 8f, lineY),
                        end = Offset(scanBoxLeft + scanBoxWidth - 8f, lineY),
                        strokeWidth = 2f
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

                IconButton(
                    onClick = { isTorchOn = !isTorchOn },
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