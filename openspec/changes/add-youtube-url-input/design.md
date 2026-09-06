## Context

See `proposal.md` — Why. Requirements are in `specs/remote-media-import/spec.md`.

The constraint that shapes this entire design is a structural property of the existing app: all four
workflows read a single `tk.StringVar` (`LeftPanel._selected_path`), and every consumer below it —
Whisper, `cv2.VideoCapture`, `ffmpeg.input`, the OCR extractor, the visual and vision analysers —
requires a local file path. None can accept a URL.

```
  [Select File]  --+
  [Drag + Drop]  --+--> selected_path (StringVar) --+
  [Recent files] --+                                |
  [Paste URL] *NEW*--> [fetch] --> local path ------+
                                                    |
        +-------------------------------------------+
        |
        v            v              v                  v
   Transcribe      Clips      Content Plan          Chapters
   (local path) (local path)  (local path)     (transcript text only)
```

Because the fetch resolves a URL to a local file *before* `selected_path` is written, everything
below that variable is untouched by this change.

Three existing behaviours constrain the design and are easy to miss:

- `FileHandler.save_transcription()` derives its output path from the source file
  (`os.path.splitext(source_path)[0] + "_transcription.srt"`). The download destination therefore
  silently determines where transcripts are written.
- `SUPPORTED_VIDEO_EXTENSIONS` contains exactly one entry, `.mp4`. A `.webm` or `.mkv` download would
  make `is_video()` return `False`, silently suppressing the thumbnail.
- Cancellation is cooperative and currently checked only *between* stages, so no existing operation
  can be interrupted mid-run.

## Goals / Non-Goals

**Goals**
- Zero changes to controllers, services, the cutter, or analysis strategies.
- Fetch behaves like every other long-running operation: background thread, `on_stage` / `on_log`
  callbacks, shared cancel event, no widget access off the main thread.
- Absent `yt-dlp`, the app behaves exactly as it does today.

**Non-Goals**
- Playlist or batch download (explicitly rejected; see spec).
- Authentication, cookie import, or any bypass of platform restrictions.
- Resumable or parallel downloads.
- A determinate progress bar. The existing bar is indeterminate and stays that way; percentage is
  reported through the activity log and stage text instead.

## Decisions

### 1. Resolve the URL to a file *before* it enters the pipeline

**Decision.** The fetch is a self-contained operation that ends by calling the same
`FilePicker._set_file(path)` used by the browse, drop, and recent-file paths.

**Why.** It makes the blast radius one module plus one widget. The alternative — teaching each
controller to accept a URL and download as "Step 0" — would push network concerns into three
controllers and every domain service, and would re-download on each workflow run.

**Alternative considered.** Streaming directly from a URL into ffmpeg. Rejected: `cv2.VideoCapture`
cannot consume it, so Clips, OCR, and the visual strategies would all break, and every workflow
would re-fetch.

### 2. `yt-dlp`, imported optionally

**Decision.** Depend on `yt-dlp`, imported behind a `try/except ImportError` guard exposing an
`is_available()` predicate, mirroring `src/transcription/diarizer.py`.

**Why.** It is the only actively maintained library for this task. The optional-import guard matches
the established convention (`tkinterdnd2` in `app.py`, `pyannote` in `diarizer.py`) and keeps a
network dependency from becoming a hard startup requirement.

**Alternative considered.** `pytube` — frequently broken by upstream changes, effectively unmaintained.
Shelling out to a `yt-dlp` binary — loses the Python progress-hook API that makes cancellation work.

### 3. Force `.mp4` output rather than widening the supported extensions

**Decision.** Request an mp4-compatible format and set `merge_output_format="mp4"`. Audio-only
fetches produce `.m4a`, already present in `SUPPORTED_AUDIO_EXTENSIONS`.

**Why.** `SUPPORTED_VIDEO_EXTENSIONS` is read by `is_video()` (thumbnails) and by the drag-drop
extension gate. Widening it would imply the cutter and OCR paths were validated against `.webm` and
`.mkv`, which they have not been. Forcing mp4 keeps the fetched file identical in kind to what users
already feed the app. Merging requires ffmpeg, which is already a hard requirement.

**Trade-off.** Occasionally forgoes a marginally higher-quality VP9/AV1 stream. Acceptable.

### 4. A `DownloadController`, not a direct worker call

**Decision.** Add `src/controllers/download.py` following the existing controller shape: a `run(...)`
that spawns a `daemon=True` thread and reports via `on_start` / `on_stage` / `on_success` /
`on_error` / `on_done` / `on_log`.

**Why.** Fetch is a user-initiated, cancellable, long-running workflow — exactly what controllers
exist for. The `App._chapters_worker` precedent of calling a domain function directly is the
codebase's one exception and does not support cancellation, which this operation needs.

### 5. Real mid-download cancellation via the progress hook

**Decision.** The shared `threading.Event` is checked inside yt-dlp's `progress_hook`, which raises
to abort the transfer. The exception is translated into the app's `OperationCancelledError`.

**Why.** The hook fires continuously during transfer, making this the first operation in the app that
can stop promptly rather than at the next stage boundary. The domain module still owns no knowledge
of the UI — it receives the event as a parameter, exactly as the other controllers do.

Partial `.part` files are removed in the cancellation path so a cancelled fetch leaves nothing behind.

### 6. Resolve the download folder on the main thread, before the worker starts

**Decision.** If no folder is configured, `filedialog.askdirectory()` is called from the UI layer
*before* `DownloadController.run(...)` is invoked. The worker receives an already-resolved path.

**Why.** Tkinter dialogs must not be opened from a background thread. This is a hard ordering
constraint, not a stylistic preference. The chosen folder persists via `settings.save(download_dir=…)`.

### 7. Accept any http(s) URL; let the extractor decide what it supports

**Decision.** Validate only that the input is a well-formed http/https URL, reject a URL that
identifies a *playlist*, and let yt-dlp report an unsupported site as an actionable error. A single
video URL that merely carries a `list=` parameter is downloaded as one video via `noplaylist=True`.

**Why.** A strict YouTube-only regex would reject valid `youtu.be`, `/shorts/`, and `/live/` forms
while adding no safety, since the extractor is the real authority. Distinguishing a playlist URL from
a video-within-a-playlist URL prevents the common surprise of pasting a link from a playlist page and
getting either a rejection or 200 videos.

### 8. Detect audio-only by extension, adding no new state

**Decision.** The guard for video-requiring workflows tests the selected file's extension against the
existing `SUPPORTED_AUDIO_EXTENSIONS`.

**Why.** It requires no new field, needs no persistence, and — usefully — also catches a user who
selects a local `.mp3` from disk and tries to generate clips, which currently fails deep inside
OpenCV with an opaque error.

### 9. Throttle progress logging

**Decision.** Log download progress at coarse intervals (roughly every 10%) rather than on every hook
invocation.

**Why.** The hook fires many times per second. `ActivityLogPanel.append` marshals each call through
`root.after(0, …)` onto the main thread, so unthrottled logging would flood the event loop and make
the UI stutter during every download.

## Risks / Trade-offs

- **yt-dlp breaks when YouTube changes** → Errors surface as actionable messages; document the
  `pip install -U yt-dlp` remedy in the README and in the failure message itself.
- **Bot-detection / HTTP 429 throttling** → Report the specific failure rather than retrying blindly.
  Cookie-based authentication is an explicit non-goal and a possible later change.
- **Large downloads fill the destination disk** → Surface the write failure clearly; the audio-only
  option gives users a low-cost path for transcript-only work.
- **Download destination silently relocates all transcripts and clip folders** → Made explicit in the
  spec, prompted for on first use, and worth stating in the UI near the URL input.
- **Progress hook raising through third-party code** → Guarantee cleanup of partial files in a
  `finally` block rather than relying on the library's own unwind behaviour.
- **New network dependency in an otherwise offline-capable app** → Confined to one optional module;
  every existing local workflow is unaffected when it is absent.

## Migration Plan

Additive, no migration required. No existing file, setting, or output path changes meaning.

- `yt-dlp` is added to `requirements.txt` as an optional, commented dependency, matching the existing
  treatment of `pyannote.audio`, so existing environments are not forced to install it.
- Rollback is removal of the new module, controller, and the URL widget; nothing else references them.
- The new `download_dir` settings key is read with a default and ignored by older builds, so settings
  files remain compatible in both directions.
