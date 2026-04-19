Read and explain `src/models.py` — the shared data models and configuration constants.

Steps:
1. Read the file at `src/models.py`.

2. For every enum, dataclass, and NamedTuple, explain:
   - What it represents in the domain
   - Which values/fields it defines
   - Which modules use it (GRASP Information Expert role)

   Cover: `ExportFormat`, `AspectRatio`, `AnalysisStrategy`, `ClipMode`, `Segment`, `ClipResult`, `ClaudeModel`, `FILLER_WORDS`, `TRAILING_CONNECTORS`, `LEADING_CONNECTORS`.

3. List every module-level constant (`DEFAULT_*`, `WHISPER_MODELS`, `THUMBNAIL_SIZE`, `WINDOW_TITLE`, etc.), its current value, and what it controls.

4. Explain `ClipResult.timestamp_label` and why computed properties belong here rather than in the UI or controller.

5. Note that `OperationCancelledError` lives in `src/controllers/__init__.py` (not here) — explain the boundary decision.
