package com.videotriage.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.videotriage.app.VideoTriageViewModel

/**
 * Root triage UI: a folder filter, a progress line, the swipeable video deck
 * (or a done/empty/loading state), and keep/undo/trash action buttons. Owns a
 * single shared [ExoPlayer] that follows whichever card is on top.
 */
@Composable
fun TriageScreen(vm: VideoTriageViewModel) {
    val state = vm.state
    val context = LocalContext.current

    // Load the first time this screen appears.
    LaunchedEffect(Unit) { vm.load() }

    // One reusable player for the whole session.
    val player = remember {
        ExoPlayer.Builder(context).build().apply {
            repeatMode = Player.REPEAT_MODE_ONE
            playWhenReady = true
            volume = 0f // start muted
        }
    }
    var isPlaying by remember { mutableStateOf(true) }
    var muted by remember { mutableStateOf(true) }

    LaunchedEffect(muted) { player.volume = if (muted) 0f else 1f }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }

    // Point the player at the current video whenever it changes.
    val current = state.currentVideo
    LaunchedEffect(current?.uri) {
        if (current != null) {
            player.setMediaItem(MediaItem.fromUri(current.uri))
            player.prepare()
            player.playWhenReady = true
        } else {
            player.clearMediaItems()
        }
    }

    // Pause in background, resume on return.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE -> player.pause()
                Lifecycle.Event.ON_RESUME -> if (player.mediaItemCount > 0) player.play()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // One-shot messages (errors, "freed N MB").
    val snackbarHostState = remember { SnackbarHostState() }
    LaunchedEffect(state.message) {
        state.message?.let {
            snackbarHostState.showSnackbar(it)
            vm.consumeMessage()
        }
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize(),
        ) {
            FolderFilterBar(
                buckets = state.buckets,
                selected = state.selectedBucket,
                trashCount = state.trashCount,
                trashBytes = state.trashBytes,
                onSelect = vm::selectBucket,
                onEmptyTrash = vm::emptyTrash,
            )

            if (current != null) {
                Text(
                    text = "${state.index + 1} of ${state.videos.size}   •   " +
                        "kept ${state.keptCount}   •   trashed ${state.trashedCount}",
                    style = MaterialTheme.typography.labelMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 4.dp),
                )
            }

            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(16.dp),
                contentAlignment = Alignment.Center,
            ) {
                when {
                    state.loading -> CircularProgressIndicator()
                    current != null -> SwipeableDeck(
                        cardKey = current.uri,
                        onKeep = vm::keep,
                        onTrash = vm::trash,
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        VideoCard(
                            item = current,
                            player = player,
                            isPlaying = isPlaying,
                            muted = muted,
                            onTogglePlay = { if (isPlaying) player.pause() else player.play() },
                            onToggleMute = { muted = !muted },
                            modifier = Modifier.fillMaxSize(),
                        )
                    }
                    else -> DoneScreen(
                        keptCount = state.keptCount,
                        trashedCount = state.trashedCount,
                        hadAnyVideos = state.videos.isNotEmpty(),
                        onRescan = vm::load,
                    )
                }
            }

            if (current != null) {
                ActionBar(
                    canUndo = state.canUndo,
                    onTrash = vm::trash,
                    onUndo = vm::undo,
                    onKeep = vm::keep,
                )
            }
        }
    }
}

@Composable
private fun ActionBar(
    canUndo: Boolean,
    onTrash: () -> Unit,
    onUndo: () -> Unit,
    onKeep: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Button(
            onClick = onTrash,
            colors = ButtonDefaults.buttonColors(containerColor = TrashRed),
        ) {
            Icon(Icons.Filled.Close, contentDescription = null)
            Text("  Trash")
        }

        TextButton(onClick = onUndo, enabled = canUndo) {
            Icon(Icons.AutoMirrored.Filled.Undo, contentDescription = null)
            Text("  Undo")
        }

        Button(
            onClick = onKeep,
            colors = ButtonDefaults.buttonColors(containerColor = KeepGreen),
        ) {
            Icon(Icons.Filled.Favorite, contentDescription = null)
            Text("  Keep")
        }
    }
}
