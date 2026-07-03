package com.videotriage.app.ui

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.videotriage.app.data.Bucket

private const val ALL_FOLDERS = "All folders"

/**
 * Top control bar: a folder filter dropdown on the left and a trash summary
 * with an "Empty" action (guarded by a confirmation dialog) on the right.
 * Folders are identified by MediaStore BUCKET_ID, so same-named folders on
 * different volumes stay distinct.
 */
@Composable
fun FolderFilterBar(
    buckets: List<Bucket>,
    selected: Bucket?,
    trashCount: Int,
    trashBytes: Long,
    onSelect: (Bucket?) -> Unit,
    onEmptyTrash: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    var menuOpen by remember { mutableStateOf(false) }
    var confirmOpen by remember { mutableStateOf(false) }
    val trashSize = Formatter.formatFileSize(context, trashBytes)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        // Folder filter.
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { menuOpen = true }) {
                Text(selected?.name ?: ALL_FOLDERS, maxLines = 1)
                Icon(Icons.Filled.ArrowDropDown, contentDescription = "Choose folder")
            }
            DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                DropdownMenuItem(
                    text = { Text(ALL_FOLDERS) },
                    onClick = { menuOpen = false; onSelect(null) },
                )
                buckets.forEach { bucket ->
                    DropdownMenuItem(
                        text = { Text(bucket.name) },
                        onClick = { menuOpen = false; onSelect(bucket) },
                    )
                }
            }
        }

        // Trash summary + empty action.
        TextButton(
            onClick = { confirmOpen = true },
            enabled = trashCount > 0,
        ) {
            Icon(Icons.Filled.Delete, contentDescription = null)
            Text(
                text = "  Trash: $trashCount ($trashSize)",
                style = MaterialTheme.typography.labelLarge,
            )
        }
    }

    if (confirmOpen) {
        AlertDialog(
            onDismissRequest = { confirmOpen = false },
            title = { Text("Empty trash?") },
            text = {
                Text(
                    "Permanently delete $trashCount video(s) and free " +
                        "$trashSize? This cannot be undone."
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmOpen = false
                    onEmptyTrash()
                }) { Text("Delete permanently") }
            },
            dismissButton = {
                TextButton(onClick = { confirmOpen = false }) { Text("Cancel") }
            },
        )
    }
}
