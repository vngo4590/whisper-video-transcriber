Read and explain all three controllers in `src/controllers/`.

Steps:
1. Read all three files: `src/controllers/__init__.py`, `src/controllers/transcription.py`, `src/controllers/clips.py`, `src/controllers/content_plan.py`.

2. Explain `OperationCancelledError` (defined in `__init__.py`): why it lives in the controllers package and how every worker raises it on cancellation rather than silently exiting.

3. For `TranscriptionController`:
   - GRASP Controller: mediates the "Transcribe" system event without owning widgets or Whisper internals.
   - Callback contract: `on_start`, `on_success`, `on_error`, `on_done`, `on_log` — explain each and why callbacks decouple the controller from tkinter.
   - Cancellation: how `cancel_event: threading.Event` is passed into `run()` and checked via `_check_cancel()` between the Whisper pass and the OCR pass.
   - `on_log` forwarding: how detailed Whisper/OCR progress messages reach the ActivityLogPanel.

4. For `ClipsController`:
   - Pipeline stages (Transcribe → Moment Analysis → Claude → Snap Boundaries → Filter → Refine → Cut) and where `_check_cancel()` is called between each.
   - How `on_log` is forwarded into `ClipAnalyzer.find_viral_moments(on_log=…)` so Claude API call details appear in the Activity Log.
   - `on_stage` vs `on_log`: stage updates the sidebar label; log writes to the Activity tab.

5. For `ContentPlanController`:
   - Same pipeline pattern: Transcribe → optional Moment Analysis → `generate_plan()`.
   - How `on_log` is forwarded into `generate_plan(on_log=…)`.

6. Describe the shared threading model: daemon threads, why `root.after(0, …)` must be used in App (not in the controllers) to marshal callbacks back to the main thread.

7. Note the DIP angle: all three controllers depend on service interfaces, never on tkinter or ffmpeg directly.
