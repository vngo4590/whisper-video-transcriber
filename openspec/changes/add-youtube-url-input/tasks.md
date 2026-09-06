## 1. Dependency and constants

- [x] 1.1 Add `yt-dlp` to `requirements.txt` as an optional, commented dependency alongside the existing `pyannote.audio` entry, then verify `pip install yt-dlp` succeeds in `.venv` and `python -c "import yt_dlp; print(yt_dlp.version.__version__)"` prints a version
- [x] 1.2 Add remote-import constants to `src/models.py` — a `FetchMode` enum (video / audio-only) with labels, the default download format strings, and the default fetch mode — and verify `python -c "import src.models"` succeeds and the new names are importable
- [x] 1.3 Confirm `SUPPORTED_VIDEO_EXTENSIONS` still contains `.mp4` and `SUPPORTED_AUDIO_EXTENSIONS` contains `.m4a`, so forced-mp4 video and audio-only downloads are both recognised; verify by asserting both membership checks in a throwaway `python -c` call

## 2. URL validation

- [x] 2.1 Add URL parsing helpers to the media package — well-formed http(s) check, playlist-URL detection, and single-video-within-a-playlist detection — and verify with a `python -c` call covering a standard watch URL, a `youtu.be` short link, a `/shorts/` link, a `watch?v=…&list=…` URL (must NOT be treated as a playlist), a `/playlist?list=…` URL (must be treated as a playlist), and a non-URL string
- [x] 2.2 Add a filename sanitiser that strips characters illegal on Windows and collapses whitespace, and verify a title containing `\ / : * ? " < > |` produces a valid filename via `python -c`

## 3. Downloader module

- [x] 3.1 Create the downloader module in `src/media/` with a module docstring stating its single responsibility and SOLID/GRASP role per project convention, exposing an `is_available()` predicate behind `try: import yt_dlp except ImportError`, mirroring `src/transcription/diarizer.py`; verify `python -c "from src.media.downloader import is_available; print(is_available())"` prints `True` with yt-dlp installed
- [x] 3.2 Implement the fetch function accepting URL, destination folder, fetch mode, `cancel_event`, and optional `on_log` / `on_progress` callbacks, returning the resulting local file path; keep the module free of tkinter imports and verify with `grep -n tkinter` returning no matches in the new file
- [x] 3.3 Configure format selection so video fetches force an mp4 container via `merge_output_format="mp4"` and audio-only fetches produce `.m4a`, and set `noplaylist=True`; verify by fetching one short public video in each mode and confirming the output extension with `python -c`
- [x] 3.4 Implement the progress hook so it checks `cancel_event` on every invocation and raises to abort the transfer, translating the abort into `OperationCancelledError`; verify by setting the event partway through a download and confirming the call raises rather than running to completion
- [x] 3.5 Throttle progress logging to roughly every 10% so the hook does not flood `ActivityLogPanel`, and verify a full download emits a bounded number of progress log lines rather than one per hook call
- [x] 3.6 Guarantee cleanup of partial `.part` files in a `finally` block on both cancellation and failure, and verify the destination folder contains no leftover files after a cancelled fetch
- [x] 3.7 Map yt-dlp extraction errors to human-readable messages for private, removed, region-blocked, age-restricted, unsupported-site, live-stream, and network failures, and verify each surfaces a plain message with no raw traceback

## 4. Download controller

- [x] 4.1 Create `src/controllers/download.py` following the existing controller shape — a `run(...)` that returns immediately after spawning a `daemon=True` thread plus a private `_worker` — owning no widgets and importing no tkinter; verify with `python -c "import src.controllers.download"` and a `grep -n tkinter` returning no matches
- [x] 4.2 Implement the worker's callback contract: `on_start` / `on_stage` / `on_success` / `on_error` / `on_done` / `on_log`, with `"Step N/M — …"` stage prefixes, catching `OperationCancelledError` into `on_error("Operation was cancelled.")`, catching `Exception` into `on_error(str(exc))`, and always calling `on_done()` in `finally`; verify by reading back the worker and confirming every path reaches `on_done()`
- [x] 4.3 Verify the controller honours the shared cancel event end-to-end by starting a fetch, pressing Cancel, and confirming the activity log shows the cancellation and the app returns to idle

## 5. Settings and download destination

- [x] 5.1 Add read/write of a `download_dir` settings key using the existing `settings.get` / `settings.save` module API with no interface change, and verify a saved value survives a restart via `python -c "from src.config import settings; print(settings.get('download_dir'))"`
- [x] 5.2 Prompt for the destination with `filedialog.askdirectory()` from the UI layer *before* the worker thread starts, never from the worker, and verify the prompt appears only on first fetch and not on subsequent fetches
- [x] 5.3 Handle a configured folder that no longer exists or is unwritable by reporting the problem and re-prompting, and verify by pointing `download_dir` at a deleted path and starting a fetch

## 6. Sidebar URL input

- [x] 6.1 Add the URL entry row, Fetch button, and "Audio only (faster)" checkbox to the sidebar FILE section, persisting the fetch mode via settings; verify the controls render correctly at the default window size and after resizing the sidebar pane
- [x] 6.2 Route a successful fetch through the existing `FilePicker._set_file(path)` so the file becomes the active selection; verify the filename label updates, a thumbnail appears, and the file is added to the recent-files list
- [x] 6.3 Disable the URL input with an explanatory hint when `is_available()` is `False`, following the graceful-degradation convention; verify by temporarily renaming the installed `yt_dlp` package and confirming the app still starts and all local-file workflows work
- [x] 6.4 Reject empty input and playlist URLs in the submit handler with clear messages and no download attempt; verify by submitting an empty field and a `/playlist?list=…` URL
- [x] 6.5 Include the URL controls in `set_busy()` so they are disabled while any job runs, and verify they grey out during a transcription and re-enable when it finishes
- [x] 6.6 If `src/ui/sidebar/file_picker.py` exceeds the project's ~200-line soft limit, split the URL controls into a sibling module rather than growing the file, and verify the final line count with `(Get-Content <file>).Count`

## 7. App wiring

- [x] 7.1 Construct the `DownloadController` in `App.__init__` and wire its callbacks, per the project rule that `App` is the only wiring point; verify `python -c "import src.ui.app"` succeeds with no circular-import error
- [x] 7.2 Marshal every fetch result back to the UI via `self._root.after(0, lambda: …)` and select the Activity tab on start using the existing `_start_job()` helper; verify no widget is touched from the worker thread by reviewing each callback
- [x] 7.3 Add the audio-only guard so starting Video Clips, on-screen-text extraction, or a visual analysis strategy with an audio-only selection warns the user before the workflow begins; verify by fetching audio-only and attempting each of the three, and confirm a local `.mp3` selected from disk triggers the same warning

## 8. End-to-end verification

- [x] 8.1 Run `python -m compileall src main.py` and confirm it reports no errors
- [x] 8.2 Run `python -c "import src.ui.app"` and `python -c "import src.clips.analyzer"` and confirm both succeed, catching circular imports and prompt-loading regressions
- [x] 8.3 Fetch a short public video, transcribe it, and verify the transcript is written into the configured download folder next to the media file
- [x] 8.4 Generate clips from a fetched video and verify cutting, aspect-ratio conversion, and caption burn-in all succeed on the downloaded mp4
- [x] 8.5 Fetch with audio-only, transcribe it, and verify the transcript succeeds while the video-requiring workflows warn as specified
- [x] 8.6 Verify cancellation during download via both the Cancel button and the `Escape` shortcut, confirming prompt termination and no leftover partial files

## 9. Documentation

- [x] 9.1 Update `README.md` with the URL input, the optional `yt-dlp` install step, the `pip install -U yt-dlp` remedy for extraction failures, and a note that downloaded media and its transcripts share a folder; verify by re-reading the rendered file
- [x] 9.2 Update `.github/copilot-instructions.md` to record `yt-dlp` as an optional dependency and note that fetched media enters through the same `selected_path` chokepoint; verify the External requirements section reflects the new dependency
