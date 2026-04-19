Read and explain all UI modules across `src/ui/`.

Steps:
1. Read all UI files:
   - `src/ui/app.py`, `src/ui/theme.py`
   - `src/ui/sidebar/panel.py`, `src/ui/sidebar/file_picker.py`, `src/ui/sidebar/widgets.py`
   - `src/ui/sidebar/tabs/transcribe.py`, `src/ui/sidebar/tabs/video_clips.py`, `src/ui/sidebar/tabs/content_plan.py`
   - `src/ui/panels/transcript.py`, `src/ui/panels/clips.py`, `src/ui/panels/content_plan.py`, `src/ui/panels/activity_log.py`
   - `src/ui/shared/api_settings.py`, `src/ui/shared/strategy_picker.py`

2. Describe `App` (app.py):
   - How it creates all three controllers, the shared `_cancel_event`, and wires every callback.
   - The four-tab right notebook (Transcript, Clips, Content Plan, Activity) and which tab auto-selects for each operation.
   - `_start_job()`: clears the cancel event, clears the activity log, switches to the Activity tab.
   - `_on_cancel_requested()`: sets `_cancel_event` so the active worker stops after its current stage.
   - `_on_log()`: routes `(message, level)` to `ActivityLogPanel.append()`.
   - `_on_error()`: distinguishes "Operation was cancelled." (no dialog, just logs) from real errors (messagebox).

3. Describe `LeftPanel` (sidebar/panel.py):
   - Public API: `set_busy()`, `show_loading()`, `set_stage()`.
   - The Cancel button: when it appears/disappears, what `_handle_cancel()` does (immediate label feedback + forwards to `on_cancel`).
   - How `set_stage()` updates the wrapping status label mid-operation.

4. Describe each sidebar tab (`TranscribeTab`, `VideoClipsTab`, `ContentPlanTab`):
   - What settings each owns and what it passes up through its callback.
   - For `TranscribeTab`: the "Extract on-screen text (OCR)" checkbox and the `extract_onscreen` flag it adds to the callback.

5. Describe each right panel:
   - `RightPanel` (transcript.py): `set_text()` API.
   - `ClipsPanel` (clips.py): `add_clip()`, `set_stage()`, `show_loading()`, `reset()`.
   - `ContentPlanPanel` (content_plan.py): `set_text()`, `set_stage()`, `show_loading()`, `reset()`.
   - `ActivityLogPanel` (activity_log.py): `append(message, level)` thread-safety via `root.after(0, …)`, `clear()`, the colour-coded tag system.

6. Draw the complete data-flow for a Transcribe run:
   user click → TranscribeTab._handle_submit → App._on_transcribe_requested → App._start_job (clear event, clear log, switch to Activity tab) → TranscriptionController.run → background thread → on_log → ActivityLogPanel → on_success → RightPanel.set_text + switch to Transcript tab.
