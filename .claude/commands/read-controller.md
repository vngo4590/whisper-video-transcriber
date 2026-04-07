Read and explain `src/controller.py` — the transcription workflow controller.

Steps:
1. Read the file at `src/controller.py`.
2. Explain the GRASP Controller pattern: how `TranscriptionController` mediates the "Transcribe" system event without owning any widgets or Whisper internals.
3. Describe the callback contract (`on_start`, `on_success`, `on_error`, `on_done`) and why callbacks are used instead of direct widget references (Low Coupling).
4. Explain the threading model: why the worker is a daemon thread and how results are routed back to the UI thread via callbacks.
5. Note the DIP angle: the controller depends on `TranscriptionService` and `FileHandler` interfaces, not on their implementations.
