Give a full architectural overview of this project.

Steps:
1. Read every source file across these packages:
   - Entry point: `main.py`
   - Config & models: `src/models.py`, `src/config/settings.py`
   - Transcription: `src/transcription/service.py`, `src/transcription/file_handler.py`, `src/transcription/ocr_extractor.py`, `src/transcription/merger.py`, `src/transcription/_srt_utils.py`
   - Controllers: `src/controllers/__init__.py`, `src/controllers/transcription.py`, `src/controllers/clips.py`, `src/controllers/content_plan.py`
   - Clips pipeline: `src/clips/analyzer.py`, `src/clips/cutter.py`, `src/clips/word_refiner.py`
   - Analysis: `src/analysis/detector.py`, `src/analysis/audio.py`, `src/analysis/visual.py`, `src/analysis/vision.py`, `src/analysis/content_planner.py`, `src/analysis/chapters.py`
   - Media: `src/media/utils.py`
   - UI app & theme: `src/ui/app.py`, `src/ui/theme.py`
   - UI sidebar: `src/ui/sidebar/panel.py`, `src/ui/sidebar/file_picker.py`, `src/ui/sidebar/widgets.py`, `src/ui/sidebar/tabs/transcribe.py`, `src/ui/sidebar/tabs/video_clips.py`, `src/ui/sidebar/tabs/content_plan.py`
   - UI panels: `src/ui/panels/transcript.py`, `src/ui/panels/clips.py`, `src/ui/panels/content_plan.py`, `src/ui/panels/activity_log.py`, `src/ui/panels/chapters.py`
   - Shared UI: `src/ui/shared/api_settings.py`, `src/ui/shared/strategy_picker.py`

2. Produce a module map: for each file show its single responsibility and which other modules it imports from.

3. Explain which SOLID principles and GRASP patterns apply and where in the code.

4. Describe the full request/response flow for each of the four operations:
   a. "User clicks Transcribe" → transcript appears in the Transcript tab (editable; filler-word stats shown; output_path stored for Save edits)
   b. "User clicks Generate Clips" → clip cards appear in the Clips tab (each card has Burn captions button for single-segment clips)
   c. "User clicks Generate Plan" → content plan appears in the Content Plan tab
   d. "User clicks Generate Chapters" → chapter cards appear in the Chapters tab (triggered from the Transcript panel header after transcription)

5. Describe the cancellation model: how `threading.Event` flows from the Cancel button through `App._on_cancel_requested` → `cancel_event.set()` → each controller worker's `_check_cancel()`, and what `OperationCancelledError` does.

6. Describe the Activity Log: what `on_log` callbacks emit, how `ActivityLogPanel.append()` marshals from background threads via `root.after(0, …)`, and the colour-coded level system (stage/api/detail/success/warn/error).

7. Describe the on-screen text extraction feature: `OcrExtractor.extract()` → `OcrEntry` list → `TranscriptMerger` pipeline; frame sampling with OpenCV, consecutive-text deduplication, and labelled SRT/plain-text output (`[SPEECH]` / `[ON-SCREEN]`).

8. Describe the new features added:
   - Recent files: `settings.get_recent_files()` / `settings.add_recent_file()` persisted in JSON; shown in `FilePicker` as clickable rows.
   - Drag-and-drop: `tkinterdnd2` registered on the file card; `App` uses `TkinterDnD.Tk()` with graceful fallback to `tk.Tk()`.
   - Keyboard shortcuts: `Ctrl+Enter` → `LeftPanel.submit_active()`; `Escape` → cancel; `Ctrl+Tab` → cycle right notebook tabs.
   - Editable transcript: `RightPanel` is always editable; "Save edits" writes current content back to `output_path`; filler-word stats bar computed from `FILLER_WORDS` via regex.
   - Stage counter: controllers prefix every `on_stage` call with "Step N/M —" so the sidebar always shows pipeline position.
   - Chapter segmentation: `src/analysis/chapters.py` → `generate_chapters()`; `ChaptersPanel` (5th right tab); triggered from Transcript panel "Generate Chapters" button; reads API key from `settings.get("api_key")`.
   - Caption burn-in: `VideoCutter.burn_captions()` parses the source SRT, filters and shifts timestamps to the clip timeline, re-encodes with ffmpeg `subtitles` filter; exposed per single-segment clip card in `ClipsPanel`.

9. Identify the most likely extension points for new features (e.g. different ASR backend, new analysis strategy, new export format, new right-panel tab).
