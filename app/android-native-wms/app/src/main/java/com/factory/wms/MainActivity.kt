package com.factory.wms

import android.Manifest
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
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
            requestPermissions(
                arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO),
                REQUEST_STARTUP_PERMISSIONS
            )
        }
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

    private companion object {
        private const val REQUEST_STARTUP_PERMISSIONS = 3001
    }
}
