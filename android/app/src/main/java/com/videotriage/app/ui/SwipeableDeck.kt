package com.videotriage.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * A single draggable card. Drag past the horizontal threshold (or fling) to
 * the right to [onKeep] or to the left to [onTrash]; release short of the
 * threshold to spring back. Colored KEEP / TRASH labels fade in with the drag.
 *
 * @param cardKey identifies the current top item; when it changes the card
 *                resets to center so the next video starts fresh.
 */
@Composable
fun SwipeableDeck(
    cardKey: Any,
    onKeep: () -> Unit,
    onTrash: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    BoxWithConstraints(modifier = modifier) {
        val widthPx = constraints.maxWidth.toFloat()
        val threshold = widthPx * 0.28f
        val scope = rememberCoroutineScope()
        val offsetX = remember { Animatable(0f) }

        // Reset position when a new card becomes the top card.
        LaunchedEffect(cardKey) { offsetX.snapTo(0f) }

        val rotation = (offsetX.value / widthPx) * 12f
        val keepAlpha = (offsetX.value / threshold).coerceIn(0f, 1f)
        val trashAlpha = (-offsetX.value / threshold).coerceIn(0f, 1f)

        Box(
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer {
                    translationX = offsetX.value
                    rotationZ = rotation
                }
                .pointerInput(cardKey) {
                    detectDrag(
                        onDelta = { dx ->
                            scope.launch { offsetX.snapTo(offsetX.value + dx) }
                        },
                        onEnd = {
                            val target = offsetX.value
                            when {
                                target > threshold -> scope.launch {
                                    offsetX.animateTo(widthPx * 1.5f, tween(220))
                                    onKeep()
                                }
                                target < -threshold -> scope.launch {
                                    offsetX.animateTo(-widthPx * 1.5f, tween(220))
                                    onTrash()
                                }
                                else -> scope.launch { offsetX.animateTo(0f, tween(220)) }
                            }
                        },
                    )
                },
        ) {
            content()

            // KEEP / TRASH overlay badges.
            SwipeBadge(
                text = "KEEP",
                color = KeepGreen,
                alpha = keepAlpha,
                alignment = Alignment.TopStart,
            )
            SwipeBadge(
                text = "TRASH",
                color = TrashRed,
                alpha = trashAlpha,
                alignment = Alignment.TopEnd,
            )
        }
    }
}

@Composable
private fun androidx.compose.foundation.layout.BoxScope.SwipeBadge(
    text: String,
    color: androidx.compose.ui.graphics.Color,
    alpha: Float,
    alignment: Alignment,
) {
    Box(
        modifier = Modifier
            .align(alignment)
            .padding(24.dp)
            .alpha(alpha)
            .clip(RoundedCornerShape(8.dp))
            .background(color)
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Text(
            text = text,
            color = androidx.compose.ui.graphics.Color.White,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

/**
 * Thin wrapper over [androidx.compose.foundation.gestures.detectDragGestures]
 * exposing just the horizontal delta and an end callback.
 */
private suspend fun androidx.compose.ui.input.pointer.PointerInputScope.detectDrag(
    onDelta: (Float) -> Unit,
    onEnd: () -> Unit,
) {
    androidx.compose.foundation.gestures.detectDragGestures(
        onDragEnd = onEnd,
        onDragCancel = onEnd,
        onDrag = { change, dragAmount ->
            change.consume()
            onDelta(dragAmount.x)
        },
    )
}
