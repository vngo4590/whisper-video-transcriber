Read and explain the analysis package: `src/analysis/`.

Steps:
1. Read all six files: `src/analysis/detector.py`, `src/analysis/audio.py`, `src/analysis/visual.py`, `src/analysis/vision.py`, `src/analysis/content_planner.py`, `src/analysis/chapters.py`.

2. For `detector.py` — the strategy dispatcher:
   - `detect_moments()`: parameters, how it dispatches to audio/visual/vision sub-analysers based on the `strategies: set[AnalysisStrategy]` argument.
   - How results from multiple strategies are merged and deduplicated.
   - The `transcript_line` key each moment dict must produce (used by `ClipsController._build_timestamped_transcript()`).

3. For `audio.py` — RMS energy analysis:
   - How audio is sampled, windowed, and scored.
   - What constitutes a "peak" (multiplier above the mean).
   - Return format and how it maps to `transcript_line`.

4. For `visual.py` — OpenCV frame differencing:
   - `build_motion_windows()`: frame sampling rate, downscaling for speed, per-frame diff score.
   - Sliding window accumulation and burst detection threshold.
   - `_merge_windows()`: how adjacent/overlapping windows are collapsed.

5. For `vision.py` — Claude vision keyframe scoring:
   - How keyframes are extracted and sent to the Claude API.
   - What the prompt asks Claude to score and why this strategy is more expensive than audio/visual.
   - `on_log` usage: what API call details are emitted.

6. For `content_planner.py` — content plan generation:
   - `generate_plan()`: parameters including the new `on_log` argument.
   - How `_USER_TEMPLATE` is filled with `{focus}`, `{max_highlights}`, `{context_block}`, `{transcript}`.
   - `format_plan()`: the plain-text rendering pipeline (overview → ranked highlights → posting calendar → overall notes).
   - `_ts()` and `_wrap()` helpers.

7. For `chapters.py` — chapter/topic segmentation:
   - `generate_chapters(transcript, api_key, claude_model, max_chapters, on_log)`: loads system prompt and user template from `prompts/chapter_prompts.md`, calls Claude API, parses JSON response.
   - Return type: sorted list of chapter dicts with keys: `chapter`, `title`, `start_time`, `end_time`, `summary`, `key_points`.
   - How `on_log` is used to emit progress to the Activity Log.
   - Triggered from the Transcript panel "Generate Chapters" button via `App._on_generate_chapters_requested`.

8. Identify the extension point: how to add a new `AnalysisStrategy` — add the enum value in `models.py`, implement a module in `src/analysis/`, register it in `detector.py`.
