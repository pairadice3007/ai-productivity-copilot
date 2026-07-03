package com.videotriage.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.videotriage.app.ui.PermissionGate
import com.videotriage.app.ui.TriageScreen
import com.videotriage.app.ui.VideoTriageTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VideoTriageTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    // Only build the triage UI once storage access is granted.
                    PermissionGate {
                        val vm: VideoTriageViewModel = viewModel()
                        TriageScreen(vm)
                    }
                }
            }
        }
    }
}
