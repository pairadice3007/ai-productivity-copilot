package com.videotriage.app

import android.app.Application
import android.text.format.Formatter
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videotriage.app.data.Bucket
import com.videotriage.app.data.VideoItem
import com.videotriage.app.data.VideoRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

/** A completed trash move, kept so it can be undone. */
data class TrashedRecord(
    val item: VideoItem,
    val trashedFile: File,
    val movedBytes: Long,
)

/**
 * Immutable snapshot of everything the triage screen renders.
 *
 * The deck IS the queue: the current video is its head, keep/trash pop it,
 * and a failed trash or an undo reinserts the exact item at the head. No
 * index arithmetic exists, so interleavings of fast swipes with slow
 * background file moves cannot desynchronize position, counters, or undo.
 */
data class TriageUiState(
    val loading: Boolean = true,
    val deck: List<VideoItem> = emptyList(),
    val totalCount: Int = 0,
    val keptCount: Int = 0,
    val trashedCount: Int = 0,
    val buckets: List<Bucket> = emptyList(),
    val selectedBucketId: String? = null,
    val trashCount: Int = 0,
    val trashBytes: Long = 0,
    val undoStack: List<TrashedRecord> = emptyList(),
    val message: String? = null,
) {
    val currentVideo: VideoItem? get() = deck.firstOrNull()
    val canUndo: Boolean get() = undoStack.isNotEmpty()

    /** 1-based position of the current card within the session. */
    val position: Int get() = totalCount - deck.size + 1
}

/**
 * Owns the triage flow: loads the video list, holds the deck, and performs
 * keep / trash / undo / empty-trash actions against [VideoRepository]. All
 * disk work runs off the main thread; the repository serializes mutations.
 */
class VideoTriageViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = VideoRepository(app)

    var state by mutableStateOf(TriageUiState())
        private set

    /**
     * Full unfiltered library from the last device scan. Folder switches
     * refilter this in memory; trash/undo keep it in sync so switching
     * folders never resurrects a moved file.
     */
    private var library: List<VideoItem> = emptyList()

    init {
        // Loading here (not from the UI) means Activity recreation on
        // rotation does not rescan or reset session progress.
        load()
    }

    /** Rescans the device and restarts the session for the current filter. */
    fun load() {
        state = state.copy(loading = true)
        viewModelScope.launch {
            val (all, stats) = withContext(Dispatchers.IO) {
                repo.query() to repo.trashStats()
            }
            library = all
            val deck = filterDeck(state.selectedBucketId)
            state = state.copy(
                loading = false,
                deck = deck,
                totalCount = deck.size,
                keptCount = 0,
                trashedCount = 0,
                buckets = all.map { Bucket(it.bucketId, it.bucket) }
                    .distinct()
                    .sortedBy { it.name.lowercase() },
                trashCount = stats.count,
                trashBytes = stats.totalBytes,
                undoStack = emptyList(),
            )
        }
    }

    /** Keep the current video: pop it off the deck. */
    fun keep() {
        if (state.currentVideo == null) return
        // The undo stack survives keeps — undo reinserts the trashed item at
        // the head, so it is always safe regardless of later swipes.
        state = state.copy(
            deck = state.deck.drop(1),
            keptCount = state.keptCount + 1,
        )
    }

    /** Trash the current video: pop optimistically, move the file in background. */
    fun trash() {
        val item = state.currentVideo ?: return
        state = state.copy(
            deck = state.deck.drop(1),
            trashedCount = state.trashedCount + 1,
        )
        viewModelScope.launch {
            try {
                val (dest, size) = withContext(Dispatchers.IO) {
                    val d = repo.moveToTrash(item)
                    d to d.length()
                }
                library = library.filterNot { it.id == item.id }
                state = state.copy(
                    undoStack = state.undoStack + TrashedRecord(item, dest, size),
                    trashCount = state.trashCount + 1,
                    trashBytes = state.trashBytes + size,
                )
            } catch (e: Exception) {
                // Reinsert the exact failed item at the head so it is
                // re-offered, no matter how far the user has swiped since.
                state = state.copy(
                    deck = listOf(item) + state.deck,
                    trashedCount = (state.trashedCount - 1).coerceAtLeast(0),
                    message = "Couldn't move ${item.name}: ${e.message}",
                )
            }
        }
    }

    /** Undo the most recent trash: move the file back and re-offer the card. */
    fun undo() {
        val rec = state.undoStack.lastOrNull() ?: return
        // Pop synchronously so a double-tap can't restore the same record twice.
        state = state.copy(undoStack = state.undoStack.dropLast(1))
        viewModelScope.launch {
            val ok = withContext(Dispatchers.IO) { repo.restore(rec.item, rec.trashedFile) }
            if (ok) {
                library = library + rec.item
                state = state.copy(
                    deck = listOf(rec.item) + state.deck,
                    trashedCount = (state.trashedCount - 1).coerceAtLeast(0),
                    trashCount = (state.trashCount - 1).coerceAtLeast(0),
                    trashBytes = (state.trashBytes - rec.movedBytes).coerceAtLeast(0),
                )
            } else {
                state = state.copy(
                    undoStack = state.undoStack + rec,
                    message = "Couldn't restore ${rec.item.name}",
                )
            }
        }
    }

    /** Switch the folder filter (null = all folders); refilters in memory. */
    fun selectBucket(bucketId: String?) {
        val deck = filterDeck(bucketId)
        state = state.copy(
            selectedBucketId = bucketId,
            deck = deck,
            totalCount = deck.size,
            keptCount = 0,
            trashedCount = 0,
            // Undo records may point outside the new filter; clearing keeps
            // the deck consistent (files stay recoverable in the trash folder).
            undoStack = emptyList(),
        )
    }

    /** Permanently delete everything in the trash folder. */
    fun emptyTrash() {
        viewModelScope.launch {
            val freed = withContext(Dispatchers.IO) { repo.emptyTrash() }
            state = state.copy(
                trashCount = 0,
                trashBytes = 0,
                // Trashed files are gone; their undo records are void.
                undoStack = emptyList(),
                message = "Freed ${Formatter.formatFileSize(getApplication<Application>(), freed)}",
            )
        }
    }

    /** Clears a one-shot snackbar message after it has been shown. */
    fun consumeMessage() {
        if (state.message != null) state = state.copy(message = null)
    }

    /** Reports a playback failure to the snackbar. */
    fun reportPlaybackError(name: String) {
        state = state.copy(message = "Couldn't play $name")
    }

    private fun filterDeck(bucketId: String?): List<VideoItem> =
        if (bucketId == null) library else library.filter { it.bucketId == bucketId }
}
