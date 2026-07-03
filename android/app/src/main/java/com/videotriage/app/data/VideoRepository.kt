package com.videotriage.app.data

import android.content.Context
import android.media.MediaScannerConnection
import android.os.Environment
import android.provider.MediaStore
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.File
import java.nio.file.Files

/**
 * Reads the device's videos via MediaStore and moves them between their
 * original location and a dedicated trash folder using direct file access
 * (granted by All Files Access / MANAGE_EXTERNAL_STORAGE).
 *
 * "Deleting" never destroys a file here — it only moves it into
 * [trashDir]. Permanent deletion happens solely in [emptyTrash].
 *
 * All mutating operations are serialized through [mutex] so an Empty Trash
 * can never run concurrently with an in-flight move (which could otherwise
 * delete a half-copied file and lose the video).
 */
class VideoRepository(private val context: Context) {

    private val mutex = Mutex()

    /** Folder (on the primary shared volume) that holds videos awaiting deletion. */
    fun trashDir(): File =
        File(Environment.getExternalStorageDirectory(), TRASH_DIR_NAME)

    /**
     * Queries all videos on the device, newest first, excluding the trash
     * folder's own contents. Folder filtering happens in memory at the caller,
     * so one scan serves both the deck and the folder list.
     */
    fun query(): List<VideoItem> {
        val trashPath = trashDir().absolutePath
        val projection = arrayOf(
            MediaStore.Video.Media._ID,
            MediaStore.Video.Media.DISPLAY_NAME,
            MediaStore.Video.Media.DATA,
            MediaStore.Video.Media.SIZE,
            MediaStore.Video.Media.DURATION,
            MediaStore.Video.Media.BUCKET_DISPLAY_NAME,
            MediaStore.Video.Media.BUCKET_ID,
        )
        val sortOrder = "${MediaStore.Video.Media.DATE_ADDED} DESC"

        val results = ArrayList<VideoItem>()
        context.contentResolver.query(
            MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
            projection,
            null,
            null,
            sortOrder,
        )?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media._ID)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DISPLAY_NAME)
            val dataCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DATA)
            val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.SIZE)
            val durCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DURATION)
            val bucketCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.BUCKET_DISPLAY_NAME)
            val bucketIdCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.BUCKET_ID)

            while (cursor.moveToNext()) {
                val data = cursor.getString(dataCol) ?: continue
                val file = File(data)
                // Exact-directory comparison: only the trash folder itself is
                // excluded, not sibling folders that share the path prefix.
                if (file.parentFile?.absolutePath == trashPath) continue
                // Skip rows whose underlying file is gone (stale MediaStore entry).
                if (!file.exists()) continue

                results.add(
                    VideoItem(
                        id = cursor.getLong(idCol),
                        file = file,
                        name = cursor.getString(nameCol) ?: file.name,
                        sizeBytes = cursor.getLong(sizeCol),
                        durationMs = cursor.getLong(durCol),
                        bucket = cursor.getString(bucketCol)
                            ?: file.parentFile?.name ?: "Unknown",
                        bucketId = cursor.getString(bucketIdCol)
                            ?: (file.parentFile?.absolutePath ?: "unknown"),
                    )
                )
            }
        }
        return results
    }

    /**
     * Moves [item] into the trash folder and rescans both locations so the
     * media library stays accurate. Returns the destination file (kept by the
     * caller so the move can be undone via [restore]).
     */
    suspend fun moveToTrash(item: VideoItem): File = mutex.withLock {
        val dir = trashDir().apply { if (!exists()) mkdirs() }
        val dest = uniqueDestination(dir, item.name)
        Files.move(item.file.toPath(), dest.toPath())
        scan(item.file.absolutePath, dest.absolutePath)
        dest
    }

    /**
     * Moves a previously-trashed file back to its original location. Returns
     * true on success.
     */
    suspend fun restore(item: VideoItem, trashedFile: File): Boolean = mutex.withLock {
        if (!trashedFile.exists()) return false
        val original = item.file
        original.parentFile?.let { if (!it.exists()) it.mkdirs() }
        try {
            Files.move(trashedFile.toPath(), original.toPath())
            scan(trashedFile.absolutePath, original.absolutePath)
            true
        } catch (e: Exception) {
            false
        }
    }

    /** Number of files currently in the trash folder and their total size. */
    fun trashStats(): TrashStats {
        val files = trashDir().listFiles()?.filter { it.isFile } ?: emptyList()
        return TrashStats(count = files.size, totalBytes = files.sumOf { it.length() })
    }

    /**
     * Permanently deletes every file in the trash folder. Returns the number
     * of bytes freed. This is the only operation that destroys data; the
     * [mutex] guarantees it never overlaps an in-flight move.
     */
    suspend fun emptyTrash(): Long = mutex.withLock {
        var freed = 0L
        val paths = ArrayList<String>()
        trashDir().listFiles()?.forEach { f ->
            if (f.isFile) {
                val size = f.length()
                if (f.delete()) {
                    freed += size
                    paths.add(f.absolutePath)
                }
            }
        }
        if (paths.isNotEmpty()) scan(*paths.toTypedArray())
        freed
    }

    // --- helpers -----------------------------------------------------------

    /** Picks a non-colliding destination name inside [dir] for [name]. */
    private fun uniqueDestination(dir: File, name: String): File {
        var candidate = File(dir, name)
        if (!candidate.exists()) return candidate
        val base = candidate.nameWithoutExtension
        val ext = candidate.extension.let { if (it.isEmpty()) "" else ".$it" }
        var i = 1
        while (candidate.exists()) {
            candidate = File(dir, "${base}_$i$ext")
            i++
        }
        return candidate
    }

    /** Asks the system to rescan paths so MediaStore reflects the move. */
    private fun scan(vararg paths: String) {
        MediaScannerConnection.scanFile(context, paths, null, null)
    }

    data class TrashStats(val count: Int, val totalBytes: Long)

    companion object {
        const val TRASH_DIR_NAME = "VideoTriage_Trash"
    }
}
