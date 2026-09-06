## Why

The app can only transcribe media that already exists on disk. Every YouTube source therefore
requires a manual out-of-band download before any of the app's four workflows can touch it, which
is the single most common way a user currently arrives at a video worth clipping. Accepting a
pasted YouTube URL removes that manual step and makes the app usable directly against the source
most of its AI features were designed for.

## What Changes

- Add a **URL input** to the sidebar's FILE section, alongside the existing Select File / drag-drop
  / recent-files entry points. Pasting a YouTube URL and confirming fetches the media and selects
  it exactly as if the user had picked it from disk.
- Add a **remote media fetcher** built on `yt-dlp`, which resolves a URL to a local `.mp4` and
  reports progress and errors through the existing activity-log and stage callbacks.
- Fetch **full video (mp4) by default**, with an explicit **"Audio only (faster)"** opt-in. Video is
  the default because the Clips, on-screen-text (OCR), and visual/vision analysis strategies all
  require real pixels; an audio-only default would silently fail the moment the user switched tabs.
- Add a **download folder setting**. The user is asked once for a destination and the choice is
  remembered. This is not cosmetic: `FileHandler.save_transcription()` writes the transcript
  alongside the source file, so the download destination also determines where every transcript,
  SRT, and clip folder for that video is written.
- **Reject playlist URLs** with a clear message. Batch transcription of a playlist is a materially
  larger feature and is explicitly out of scope here.
- Make the downloaded file a **first-class selection**: it appears in the filename label, produces a
  thumbnail, and is added to recent files, identical to a locally chosen file.
- Support **cancellation during download**. This is the first operation in the app that can be
  interrupted mid-stage rather than only between stages.
- `yt-dlp` is added as an **optional dependency**. When it is absent the URL input is disabled with
  an explanatory hint, following the app's existing graceful-degradation pattern
  (`tkinterdnd2`, `pyannote.audio`).

Not breaking. All existing entry points, workflows, and outputs are unchanged.

## Capabilities

### New Capabilities
- `remote-media-import`: Accepting a remote media URL, resolving it to a local media file the
  existing pipelines can consume, and reporting progress, cancellation, and failure. Covers URL
  validation, fetch mode (video vs audio-only), download destination, filename safety, and the
  handoff into the app's existing file-selection state.

### Modified Capabilities
<!-- None. No existing spec files are present under openspec/specs/, and no existing requirement
     changes: the transcription, clips, content-plan, and chapters workflows continue to operate on
     a local media path exactly as they do today. -->

## Impact

**New code**
- A remote-media fetch module in the domain layer (no tkinter, callback-only reporting), consistent
  with the existing `transcription` / `clips` / `analysis` / `media` package boundaries.
- A URL-entry widget in `src/ui/sidebar/file_picker.py` (or a sibling module if the file exceeds the
  project's ~200-line soft limit).

**Modified code**
- `src/ui/sidebar/file_picker.py` — new URL row; reuse of the existing `_set_file()` path so the
  fetched file flows into the shared `selected_path` StringVar.
- `src/ui/app.py` — wiring for the fetch workflow and its callbacks, per the project's rule that
  `App` is the only wiring point.
- `src/models.py` — new constants (fetch modes, URL patterns, download-related defaults).
- `src/config/settings.py` — consumers of a new persisted download-folder key. No API change; the
  module's existing `get`/`save` interface already covers it.
- `requirements.txt` — `yt-dlp` recorded as an optional dependency.
- `README.md` and `.github/copilot-instructions.md` — document the new external dependency.

**Key integration point**
- `selected_path` (a single `tk.StringVar` in `LeftPanel`) is the sole chokepoint that every
  workflow reads. Because the fetcher resolves a URL to a local path *before* that variable is set,
  the transcription service, clip cutter, OCR extractor, and analysis strategies require no changes.

**Dependencies and risks**
- `yt-dlp` is a new runtime dependency that requires periodic updates to keep working against
  YouTube; it is the only maintained option for this job.
- Extraction can fail for reasons outside the app's control (age restriction, region blocks, bot
  checks, live streams, private or removed videos). These must surface as clear, actionable errors
  rather than generic stack traces.
- `SUPPORTED_VIDEO_EXTENSIONS` currently contains only `.mp4`, so the fetch must produce `.mp4` or
  the thumbnail and video-detection paths will silently no-op.
- Video titles routinely contain characters that are illegal in Windows filenames and must be
  sanitised before they are used as a filename.
- Downloading copyrighted material is the user's responsibility; the app should not encourage
  circumventing platform restrictions.
