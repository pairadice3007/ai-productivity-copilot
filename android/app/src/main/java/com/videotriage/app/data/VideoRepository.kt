package com.videotriage.app.data

import android.content.ContentUris
import android.content.Context
import android.media.MediaScannerConnection
import android.os.Environment
import android.provider.MediaStore
import java.io.File

/**
 * Reads the device's videos via MediaStore and moves them between their
 * original location and a dedicated trash folder using direct file access
 * (granted by All Files Access / MANAGE_EXTERNAL_STORAGE).
 *
 * "Deleting" never destroys a file here — it only moves it into
 * [trashDir]. Permanent deletion happens solely in [emptyTrash].
 */
class VideoRepository(private val context: Context) {

    /** Folder (on the primary shared volume) that holds videos awaiting deletion. */
    fun trashDir(): File =
        File(Environment.getExternalStorageDirectory(), TRASH_DIR_NAME)

    /**
     * Queries all videos on the device, newest first, excluding anything that
     * already lives in the trash folder.
     *
     * @param bucket if non-null, only videos whose folder name equals this.
     */
    fun query(bucket: String? = null): List<VideoItem> {
        val trashPath = trashDir().absolutePath
        val projection = arrayOf(
            MediaStore.Video.Media._ID,
            MediaStore.Video.Media.DISPLAY_NAME,
            MediaStore.Video.Media.DATA,
            MediaStore.Video.Media.SIZE,
            MediaStore.Video.Media.DURATION,
            MediaStore.Video.Media.BUCKET_DISPLAY_NAME,
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

            while (cursor.moveToNext()) {
                val data = cursor.getString(dataCol) ?: continue
                // Skip videos already in the trash folder.
                if (data.startsWith(trashPath)) continue

                val file = File(data)
                // Skip rows whose underlying file is gone (stale MediaStore entry).
                if (!file.exists()) continue

                val bucketName = cursor.getString(bucketCol) ?: file.parentFile?.name ?: "Unknown"
                if (bucket != null && bucketName != bucket) continue

                val id = cursor.getLong(idCol)
                results.add(
                    VideoItem(
                        id = id,
                        uri = ContentUris.withAppendedId(
                            MediaStore.Video.Media.EXTERNAL_CONTENT_URI, id
                        ),
                        file = file,
                        name = cursor.getString(nameCol) ?: file.name,
                        sizeBytes = cursor.getLong(sizeCol),
                        durationMs = cursor.getLong(durCol),
                        bucket = bucketName,
                    )
                )
            }
        }
        return results
    }

    /** Distinct folder names that contain videos, sorted alphabetically. */
    fun listBuckets(): List<String> =
        query().map { it.bucket }.distinct().sorted()

    /**
     * Moves [item] into the trash folder and rescans both locations so the
     * media library stays accurate. Returns the destination file (kept by the
     * caller so the move can be undone via [restore]).
     */
    fun moveToTrash(item: VideoItem): File {
        val dir = trashDir().apply { if (!exists()) mkdirs() }
        val dest = uniqueDestination(dir, item.name)
        moveFile(item.file, dest)
        scan(item.file.absolutePath, dest.absolutePath)
        return dest
    }

    /**
     * Moves a previously-trashed file back to its original location. Returns
     * true on success.
     */
    fun restore(item: VideoItem, trashedFile: File): Boolean {
        if (!trashedFile.exists()) return false
        val original = item.file
        original.parentFile?.let { if (!it.exists()) it.mkdirs() }
        return try {
            moveFile(trashedFile, original)
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
     * of bytes freed. This is the only operation that destroys data.
     */
    fun emptyTrash(): Long {
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
        return freed
    }

    // --- helpers -----------------------------------------------------------

    /** Picks a non-colliding destination name inside [dir] for [name]. */
    private fun uniqueDestination(dir: File, name: String): File {
        var candidate = File(dir, name)
        if (!candidate.exists()) return candidate
        val dot = name.lastIndexOf('.')
        val base = if (dot > 0) name.substring(0, dot) else name
        val ext = if (dot > 0) name.substring(dot) else ""
        var i = 1
        while (candidate.exists()) {
            candidate = File(dir, "${base}_$i$ext")
            i++
        }
        return candidate
    }

    /**
     * Moves a file, preferring an instant rename and falling back to
     * copy-then-delete when source and destination are on different volumes.
     */
    private fun moveFile(src: File, dest: File) {
        if (src.renameTo(dest)) return
        src.inputStream().use { input ->
            dest.outputStream().use { output -> input.copyTo(output) }
        }
        if (!src.delete()) {
            // Copy succeeded but original couldn't be removed; surface as error
            // so the caller doesn't believe space was reclaimed.
            throw IllegalStateException("Copied ${src.name} but failed to delete original")
        }
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
