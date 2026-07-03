package com.videotriage.app.data

import java.io.File

/**
 * A single video on the device that can be triaged.
 *
 * The file itself is the single source of identity: playback uses the file
 * URI (not a MediaStore content URI, which goes stale when the file is moved
 * to trash and back), and moves operate on the same [file].
 *
 * @param id         MediaStore row id at scan time (used only as a stable UI key).
 * @param file       Absolute file on disk; used for playback and moves.
 * @param name       Display name, e.g. "VID_20240101_120000.mp4".
 * @param sizeBytes  File size in bytes.
 * @param durationMs Duration in milliseconds (0 if unknown).
 * @param bucket     Containing folder's display name, e.g. "Camera".
 * @param bucketId   MediaStore BUCKET_ID — distinguishes same-named folders
 *                   on different volumes; used for filtering.
 */
data class VideoItem(
    val id: Long,
    val file: File,
    val name: String,
    val sizeBytes: Long,
    val durationMs: Long,
    val bucket: String,
    val bucketId: String,
)

/** A folder that contains videos, identified by MediaStore BUCKET_ID. */
data class Bucket(val id: String, val name: String)
