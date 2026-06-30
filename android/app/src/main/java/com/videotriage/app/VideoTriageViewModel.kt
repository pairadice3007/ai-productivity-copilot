package com.videotriage.app

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.videotriage.app.data.VideoItem
import com.videotriage.app.data.VideoRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** Immutable snapshot of everything the triage screen renders. */
data class TriageUiState(
    val loading: Boolean = true,
    val videos: List<VideoItem> = emptyList(),
    val index: Int = 0,
    val keptCount: Int = 0,
    val trashedCount: Int = 0,
    val buckets: List<String> = emptyList(),
    val selectedBucket: String? = null,
    val trashCount: Int = 0,
    val trashBytes: Long = 0,
    val canUndo: Boolean = false,
    val message: String? = null,
) {
    val currentVideo: VideoItem? get() = videos.getOrNull(index)
    val isDone: Boolean get() = !loading && index >= videos.size
}

/**
 * Owns the triage flow: loads the video list, tracks which card is on top,
 * and performs keep / trash / undo / empty-trash actions against
 * [VideoRepository]. All disk work runs off the main thread.
 */
class VideoTriageViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = VideoRepository(app)

    var state by mutableStateOf(TriageUiState())
        private set

    /** Remembers the last trashed video so it can be moved back on undo. */
    private var lastTrashed: TrashedRecord? = null

    /** (Re)loads videos for the current folder filter and refreshes trash stats. */
    fun load() {
        state = state.copy(loading = true)
        viewModelScope.launch {
            val bucket = state.selectedBucket
            val vids = withContext(Dispatchers.IO) { repo.query(bucket) }
            val buckets = withContext(Dispatchers.IO) { repo.listBuckets() }
            val stats = withContext(Dispatchers.IO) { repo.trashStats() }
            lastTrashed = null
            state = state.copy(
                loading = false,
                videos = vids,
                index = 0,
                keptCount = 0,
                trashedCount = 0,
                buckets = buckets,
                trashCount = stats.count,
                trashBytes = stats.totalBytes,
                canUndo = false,
            )
        }
    }

    /** Keep the current video: just advance to the next card. */
    fun keep() {
        if (state.currentVideo == null) return
        lastTrashed = null
        state = state.copy(
            index = state.index + 1,
            keptCount = state.keptCount + 1,
            canUndo = false,
        )
    }

    /** Trash the current video: advance immediately, move the file in background. */
    fun trash() {
        val item = state.currentVideo ?: return
        state = state.copy(
            index = state.index + 1,
            trashedCount = state.trashedCount + 1,
        )
        viewModelScope.launch {
            try {
                val dest = withContext(Dispatchers.IO) { repo.moveToTrash(item) }
                lastTrashed = TrashedRecord(item, dest)
                refreshTrashStats(canUndo = true)
            } catch (e: Exception) {
                // Roll back the optimistic advance if the move failed.
                state = state.copy(
                    index = (state.index - 1).coerceAtLeast(0),
                    trashedCount = (state.trashedCount - 1).coerceAtLeast(0),
                    message = "Couldn't move ${item.name}: ${e.message}",
                )
            }
        }
    }

    /** Undo the most recent trash, moving the file back and returning to it. */
    fun undo() {
        val rec = lastTrashed ?: return
        viewModelScope.launch {
            val ok = withContext(Dispatchers.IO) { repo.restore(rec.item, rec.trashedFile) }
            if (ok) {
                lastTrashed = null
                state = state.copy(
                    index = (state.index - 1).coerceAtLeast(0),
                    trashedCount = (state.trashedCount - 1).coerceAtLeast(0),
                    canUndo = false,
                )
                refreshTrashStats(canUndo = false)
            } else {
                state = state.copy(message = "Couldn't restore ${rec.item.name}")
            }
        }
    }

    /** Switch the folder filter (null = all folders) and reload. */
    fun selectBucket(bucket: String?) {
        state = state.copy(selectedBucket = bucket)
        load()
    }

    /** Permanently delete everything in the trash folder. */
    fun emptyTrash() {
        viewModelScope.launch {
            val freed = withContext(Dispatchers.IO) { repo.emptyTrash() }
            lastTrashed = null
            val stats = withContext(Dispatchers.IO) { repo.trashStats() }
            state = state.copy(
                trashCount = stats.count,
                trashBytes = stats.totalBytes,
                canUndo = false,
                message = "Freed ${formatBytes(freed)}",
            )
        }
    }

    /** Clears a one-shot snackbar message after it has been shown. */
    fun consumeMessage() {
        if (state.message != null) state = state.copy(message = null)
    }

    private suspend fun refreshTrashStats(canUndo: Boolean) {
        val stats = withContext(Dispatchers.IO) { repo.trashStats() }
        state = state.copy(
            trashCount = stats.count,
            trashBytes = stats.totalBytes,
            canUndo = canUndo,
        )
    }

    private data class TrashedRecord(val item: VideoItem, val trashedFile: File)
}
