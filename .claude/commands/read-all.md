Give a full architectural overview of this project.

Steps:
1. Read every source file across these packages:
   - Entry point: `main.py`
   - Config & models: `src/models.py`, `src/config/settings.py`
   - Transcription: `src/transcription/service.py`, `src/transcription/file_handler.py`, `src/transcription/ocr_extractor.py`, `src/transcription/merger.py`, `src/transcription/_srt_utils.py`
   - Controllers: `src/controllers/__init__.py`, `src/controllers/transcription.py`, `src/controllers/clips.py`, `src/controllers/content_plan.py`
   - Clips pipeline: `src/clips/analyzer.py`, `src/clips/cutter.py`, `src/clips/word_refiner.py`
   - Analysis: `src/analysis/detector.py`, `src/analysis/audio.py`, `src/analysis/visual.py`, `src/analysis/vision.py`, `src/analysis/content_planner.py`
   - Media: `src/media/utils.py`
   - UI app & theme: `src/ui/app.py`, `src/ui/theme.py`
   - UI sidebar: `src/ui/sidebar/panel.py`, `src/ui/sidebar/file_picker.py`, `src/ui/sidebar/widgets.py`, `src/ui/sidebar/tabs/transcribe.py`, `src/ui/sidebar/tabs/video_clips.py`, `src/ui/sidebar/tabs/content_plan.py`
   - UI panels: `src/ui/panels/transcript.py`, `src/ui/panels/clips.py`, `src/ui/panels/content_plan.py`, `src/ui/panels/activity_log.py`
   - Shared UI: `src/ui/shared/api_settings.py`, `src/ui/shared/strategy_picker.py`

2. Produce a module map: for each file show its single responsibility and which other modules it imports from.

3. Explain which SOLID principles and GRASP patterns apply and where in the code.

4. Describe the full request/response flow for each of the three operations:
   a. "User clicks Transcribe" → transcript appears in the Transcript tab
   b. "User clicks Generate Clips" → clip cards appear in the Clips tab
   c. "User clicks Generate Plan" → content plan appears in the Content Plan tab

5. Describe the cancellation model: how `threading.Event` flows from the Cancel button through `App._on_cancel_requested` → `cancel_event.set()` → each controller worker's `_check_cancel()`, and what `OperationCancelledError` does.

6. Describe the Activity Log: what `on_log` callbacks emit, how `ActivityLogPanel.append()` marshals from background threads via `root.after(0, …)`, and the colour-coded level system (stage/api/detail/success/warn/error).

7. Describe the on-screen text extraction feature: `OcrExtractor.extract()` → `OcrEntry` list → `TranscriptMerger` pipeline; frame sampling with OpenCV, consecutive-text deduplication, and labelled SRT/plain-text output (`[SPEECH]` / `[ON-SCREEN]`).

8. Identify the most likely extension points for new features (e.g. different ASR backend, new analysis strategy, new export format, new right-panel tab).
