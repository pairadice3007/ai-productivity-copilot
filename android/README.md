# VideoTriage

A dead-simple Android app for clearing video clutter. It plays each video
full-screen so you actually remember what it is, then you **swipe right to
keep** or **swipe left to trash**. Trashed videos are *moved* into a
`VideoTriage_Trash` folder — nothing is permanently deleted until you tap
**Empty Trash**.

## Why

Hundreds of videos, a full phone, and thumbnails that all look the same.
Triage them one at a time by actually watching them, and batch-delete only
once you're sure.

## Features

- 🎞️ **Plays the video on the card** (Media3/ExoPlayer), looping and muted by
  default — tap to unmute or pause.
- 👉 **Swipe right = keep**, 👈 **swipe left = trash** (or use the buttons).
- 🗑️ Trashed videos move to `Internal storage/VideoTriage_Trash/` — a soft
  delete. An **Undo** button restores the last one.
- 🧹 **Empty Trash** permanently deletes everything in that folder (with a
  confirmation) and tells you how much space you freed.
- 📁 **Folder filter** to triage just one folder (Camera, Downloads, …) at a
  time, or all videos at once.
- 📊 Live progress: how many you've reviewed, kept, and trashed.

## Requirements

- **Android Studio** (Hedgehog or newer recommended).
- A phone/emulator running **Android 8.0 (API 26)** or higher, with some
  videos on it.
- The app uses **All files access** (`MANAGE_EXTERNAL_STORAGE`) so it can move
  videos into the trash folder without a system pop-up on every file. This is
  ideal for a personal app you install yourself. (It is *not* permitted for a
  normal Google Play listing — see "Publishing" below.)

## Build & run

This project is a standard Gradle/Kotlin Android app. The Android SDK is
downloaded automatically by Android Studio.

### Option A — Android Studio (easiest)

1. Open Android Studio → **Open** → select this `android/` folder.
2. Let Gradle sync (it fetches the SDK, Gradle 8.9, and dependencies).
3. Plug in your phone with **USB debugging** enabled (Settings → Developer
   options), or start an emulator that has a few videos.
4. Press **Run ▶**.
5. On first launch, tap **Grant access** → toggle **Allow access to manage all
   files** in system settings → press back. The app re-checks automatically.

### Option B — command line APK (sideload)

```bash
cd android
./gradlew assembleDebug
# Output: app/build/outputs/apk/debug/app-debug.apk
```

Copy `app-debug.apk` to your phone and open it to install (you may need to
allow "Install unknown apps" for your file manager). Then grant **All files
access** as above.

> Note: a CI/headless environment without the Android SDK installed cannot
> build this — the SDK is required. Android Studio installs it for you.

## How it works

- `data/VideoRepository.kt` — queries videos via **MediaStore**, and
  moves/restores/deletes files directly with `java.io.File` (allowed by All
  Files Access). Moving is an instant `renameTo` within the same volume, with
  a copy-then-delete fallback across volumes. After every move it triggers a
  media rescan so your gallery stays accurate.
- `VideoTriageViewModel.kt` — holds the video list and current position, and
  exposes `keep()`, `trash()`, `undo()`, `emptyTrash()`, and the folder
  filter. All disk work runs off the main thread.
- `ui/SwipeableDeck.kt` — the Tinder-style drag gesture with KEEP/TRASH
  badges.
- `ui/VideoCard.kt` — the ExoPlayer surface plus the name/size/duration/folder
  overlay and play/mute controls.
- `ui/TriageScreen.kt` — wires it together and owns a single shared player.

The trash folder lives at `Internal storage/VideoTriage_Trash/`. You can also
browse/restore those files with any file manager if you prefer.

## Publishing (optional)

Google Play restricts `MANAGE_EXTERNAL_STORAGE`. To publish, switch the move
logic to scoped storage (`MediaStore` "trashed" flag or
`MediaStore.createTrashRequest` / `createDeleteRequest`), which prompts the
user per batch. That's a deliberate, separate change kept out of this simple
version.
