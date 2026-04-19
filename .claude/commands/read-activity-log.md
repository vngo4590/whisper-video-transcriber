Read and explain the Activity Log and cancellation system.

Steps:
1. Read these files: `src/ui/panels/activity_log.py`, `src/controllers/__init__.py`, `src/ui/sidebar/panel.py` (Cancel button section), `src/ui/app.py` (_start_job, _on_cancel_requested, _on_log, _on_error, _on_done).

2. For `ActivityLogPanel`:
   - The `_LEVEL_COLOURS` dict: list every level name, its hex colour, and when it is used.
   - `append(message, level)`: explain the `root.after(0, lambda …)` pattern and why it is required for thread safety in tkinter.
   - `_write()`: the two-tag insert pattern (timestamp in muted colour + message in level colour), the `see(END)` auto-scroll, and the placeholder-clearing logic.
   - `clear()`: what it resets and when `App._start_job()` calls it.

3. For `OperationCancelledError` (`src/controllers/__init__.py`):
   - Why it subclasses `Exception` (not `BaseException`) so bare `except Exception` handlers still catch it.
   - The pattern: workers call `_check_cancel()` between stages; the `except OperationCancelledError` branch calls `on_log(..., "warn")` then `on_error("Operation was cancelled.")`.

4. For the Cancel button (`LeftPanel`):
   - `show_loading(True/False)`: pack/pack_forget the button so it appears only while a job runs.
   - `_handle_cancel()`: immediate "Cancelling…" label + `config(state="disabled")` so double-clicks are harmless, then delegates to `on_cancel`.
   - `set_stage(text)`: how it keeps the label updated throughout long operations.

5. For `App`:
   - `_cancel_event = threading.Event()` — single shared event, cleared in `_start_job()` before each run.
   - `_on_cancel_requested()`: just calls `_cancel_event.set()` — no UI work here.
   - `_on_log(message, level)`: routes to `ActivityLogPanel.append()` (already thread-safe).
   - `_on_error()`: the special case for `"Operation was cancelled."` — logs to Activity tab only, suppresses the error messagebox.
   - `_on_done()`: re-enables the sidebar and hides the Cancel button regardless of how the job ended.

6. Describe the full cancel timeline:
   user clicks Cancel → LeftPanel._handle_cancel (label="Cancelling…", button disabled) → App._on_cancel_requested → cancel_event.set() → background worker finishes current stage → _check_cancel() raises OperationCancelledError → except block logs "cancelled" + calls on_error("Operation was cancelled.") + calls on_done → App._on_error suppresses dialog → App._on_done hides cancel button, re-enables sidebar.
