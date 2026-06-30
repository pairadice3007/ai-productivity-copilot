package com.videotriage.app.data

import android.net.Uri
import java.io.File

/**
 * A single video on the device that can be triaged.
 *
 * @param id        MediaStore row id (stable while the file stays in place).
 * @param uri       Content URI used by ExoPlayer for playback.
 * @param file      Absolute file on disk; used to move the video to trash.
 * @param name      Display name, e.g. "VID_20240101_120000.mp4".
 * @param sizeBytes File size in bytes.
 * @param durationMs Duration in milliseconds (0 if unknown).
 * @param bucket    Containing folder name, e.g. "Camera" (for the folder filter).
 */
data class VideoItem(
    val id: Long,
    val uri: Uri,
    val file: File,
    val name: String,
    val sizeBytes: Long,
    val durationMs: Long,
    val bucket: String,
)
