Read and explain all UI modules across `src/ui/`.

Steps:
1. Read all UI files:
   - `src/ui/app.py`, `src/ui/theme.py`
   - `src/ui/sidebar/panel.py`, `src/ui/sidebar/file_picker.py`, `src/ui/sidebar/widgets.py`
   - `src/ui/sidebar/tabs/transcribe.py`, `src/ui/sidebar/tabs/video_clips.py`, `src/ui/sidebar/tabs/content_plan.py`
   - `src/ui/panels/transcript.py`, `src/ui/panels/clips.py`, `src/ui/panels/content_plan.py`, `src/ui/panels/activity_log.py`, `src/ui/panels/chapters.py`
   - `src/ui/shared/api_settings.py`, `src/ui/shared/strategy_picker.py`

2. Describe `App` (app.py):
   - How it creates all three controllers, the shared `_cancel_event`, and `_is_busy` flag; wires every callback.
   - Uses `TkinterDnD.Tk()` for the root window (with `tk.Tk()` fallback) to support OS file drops.
   - The five-tab right notebook (Transcript, Clips, Content Plan, Chapters, Activity) and which tab auto-selects for each operation (indices 0–4).
   - `_start_job()`: clears the cancel event, sets `_is_busy`, clears the activity log, switches to the Activity tab (index 4).
   - `_on_cancel_requested()`: sets `_cancel_event` so the active worker stops after its current stage.
   - `_on_log()`: routes `(message, level)` to `ActivityLogPanel.append()`.
   - `_on_error()`: distinguishes "Operation was cancelled." (no dialog, just logs) from real errors (messagebox).
   - `_bind_shortcuts()`: `Ctrl+Enter` → `LeftPanel.submit_active()`; `Escape` → cancel; `Ctrl+Tab` → cycle notebook tabs.
   - `_on_generate_chapters_requested(transcript_text)`: reads API key from settings, starts a daemon thread running `generate_chapters()`, updates `ChaptersPanel` on completion.
   - `_on_transcribe_stage(text)` callback wired to `TranscriptionController` for "Step N/M —" sidebar updates.
   - `_on_transcribe_success` now passes `output_path` to `RightPanel.set_text()`.
   - `_on_generate_clips_requested` calls `self._clips.set_source_path(path)` before starting the pipeline.

3. Describe `LeftPanel` (sidebar/panel.py):
   - Public API: `set_busy()`, `show_loading()`, `set_stage()`, `submit_active()`.
   - `submit_active()`: reads `self._mode_nb.index("current")` and calls `.submit()` on the active tab (all tabs expose a `submit()` method).
   - The Cancel button: when it appears/disappears, what `_handle_cancel()` does (immediate label feedback + forwards to `on_cancel`).
   - How `set_stage()` updates the wrapping status label mid-operation (now shows "Step N/M —" strings from controllers).

4. Describe each sidebar tab (`TranscribeTab`, `VideoClipsTab`, `ContentPlanTab`):
   - All three expose a `submit()` public method (delegates to `_handle_submit()`).
   - What settings each owns and what it passes up through its callback.
   - For `TranscribeTab`: the "Extract on-screen text (OCR)" checkbox and the `extract_onscreen` flag it adds to the callback.

5. Describe each right panel:
   - `RightPanel` (transcript.py): always editable text box; `set_text(text, output_path="")` stores path for Save; `get_text()` returns current content; "Save edits" button writes back to disk; "Generate Chapters" button fires `on_generate_chapters(get_text())`; filler-word stats bar appears after content is set (regex matches against `FILLER_WORDS`).
   - `ClipsPanel` (clips.py): `add_clip(clip)`, `set_source_path(path)`, `set_stage(text)`, `show_loading(bool)`, `reset()`; each single-segment clip card has a "Burn captions" button that runs `VideoCutter.burn_captions()` in a daemon thread.
   - `ContentPlanPanel` (content_plan.py): `set_text()`, `set_stage()`, `show_loading()`, `reset()`; Copy / Save .txt / Save .md buttons.
   - `ChaptersPanel` (chapters.py): `set_chapters(chapters)`, `set_stage()`, `show_loading()`, `reset()`; builds a card per chapter with title, timestamp, summary, and up to 4 key-point bullets.
   - `ActivityLogPanel` (activity_log.py): `append(message, level)` thread-safety via `root.after(0, …)`, `clear()`, the colour-coded tag system.

6. Describe `FilePicker` (file_picker.py):
   - `_set_file(path)` is the central file-selection method: updates `selected_path`, thumbnail, recent files list.
   - `_browse()` wraps `filedialog.askopenfilename` and calls `_set_file`.
   - `_on_drop(event)` handles `<<Drop>>` events from `tkinterdnd2`: strips braces, validates extension, calls `_set_file`.
   - Recent files: stored via `settings.add_recent_file()`; displayed as up to 6 clickable labels below the file card; `_refresh_recent()` rebuilds the list after every selection.

7. Draw the complete data-flow for a Transcribe run:
   user click → TranscribeTab.submit() → App._on_transcribe_requested → App._start_job (clear event, clear log, switch to Activity tab) → TranscriptionController.run → on_start → LeftPanel.show_loading(True) → background thread → on_stage → LeftPanel.set_stage("Step 1/2…") → on_log → ActivityLogPanel → on_success → RightPanel.set_text(text, output_path) + switch to Transcript tab + messagebox.
