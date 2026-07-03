package com.videotriage.app.ui

import android.text.format.DateUtils
import android.text.format.Formatter
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.AspectRatioFrameLayout
import androidx.media3.ui.PlayerView
import com.videotriage.app.data.VideoItem

/**
 * The visible card: the playing video filling the surface, with a gradient
 * footer showing name / size / duration / folder, plus play-pause and mute
 * controls. The [player] is shared and already pointed at [item] by the screen.
 */
@OptIn(UnstableApi::class)
@Composable
fun VideoCard(
    item: VideoItem,
    player: Player,
    isPlaying: Boolean,
    muted: Boolean,
    onTogglePlay: () -> Unit,
    onToggleMute: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    // Built once per card, not on every recomposition.
    val metadata = remember(item.id) {
        DateUtils.formatElapsedTime(item.durationMs / 1000) +
            "  •  " + Formatter.formatFileSize(context, item.sizeBytes) +
            "  •  " + item.bucket
    }

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(Color.Black),
    ) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                PlayerView(ctx).apply {
                    useController = false
                    resizeMode = AspectRatioFrameLayout.RESIZE_MODE_FIT
                    setBackgroundColor(android.graphics.Color.BLACK)
                }
            },
            update = { view -> if (view.player !== player) view.player = player },
        )

        // Bottom gradient + metadata.
        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .background(
                    Brush.verticalGradient(
                        listOf(Color.Transparent, Color(0xCC000000))
                    )
                )
                .padding(16.dp),
        ) {
            Text(
                text = item.name,
                color = Color.White,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = metadata,
                    color = Color(0xFFDDDDDD),
                    style = MaterialTheme.typography.bodySmall,
                )
                Row {
                    IconButton(onClick = onTogglePlay) {
                        Icon(
                            imageVector = if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                            contentDescription = if (isPlaying) "Pause" else "Play",
                            tint = Color.White,
                        )
                    }
                    IconButton(onClick = onToggleMute) {
                        Icon(
                            imageVector = if (muted) Icons.Filled.VolumeOff
                            else Icons.Filled.VolumeUp,
                            contentDescription = if (muted) "Unmute" else "Mute",
                            tint = Color.White,
                        )
                    }
                }
            }
        }
    }
}
