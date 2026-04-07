Read and explain all UI modules: `src/ui/app.py`, `src/ui/left_panel.py`, `src/ui/right_panel.py`.

Steps:
1. Read all three files.
2. Describe `App` (app.py): how it wires `LeftPanel`, `RightPanel`, and `TranscriptionController` together via callbacks, and why App is the GRASP Controller at the UI level.
3. Describe `LeftPanel` (left_panel.py): widgets it owns, the `set_busy()` / `show_loading()` public API, and how `_handle_transcribe()` delegates upward without knowing about Whisper or file I/O.
4. Describe `RightPanel` (right_panel.py): its single responsibility (display text) and its `set_text()` API.
5. Draw the data-flow: user click → LeftPanel → App._on_transcribe_requested → Controller.run → ... → App._on_success → RightPanel.set_text.
