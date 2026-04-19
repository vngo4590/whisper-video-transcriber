Read and explain the clips pipeline: `src/clips/`.

Steps:
1. Read all three files: `src/clips/analyzer.py`, `src/clips/cutter.py`, `src/clips/word_refiner.py`.

2. For `analyzer.py` / `ClipAnalyzer`:
   - How `_load_prompts()` parses `prompts/clip_prompts.md` into a dict keyed by `## HEADING`.
   - How `_TEMPLATES` maps each `ClipMode` to its prompt section.
   - `find_viral_moments()`: parameters (including `on_log`), the `prompt_override` vs. template path, `custom_instructions` appending.
   - How the Claude API is called: model, max_tokens, system prompt, user message construction.
   - What `on_log` emits: the `→ Claude API` line (model, input chars) and the `←` response line.
   - `_validate_clips()` and `_extract_segments()`: how raw JSON is turned into `ClipResult` / `Segment` objects, clamping, per-mode segment format (single `start_time`/`end_time` vs. `segments` array).

3. For `cutter.py` / `VideoCutter`:
   - `cut_clip()`: inputs (`source_path`, `segments`, `index`, `title`, `aspect_ratio`), output path convention.
   - How multi-segment clips are assembled (concat filter or sequential cuts).
   - Aspect ratio handling: `ASPECT_RATIO_SIZES` lookup, crop/pad logic.
   - ffmpeg-python pipeline: why it is used instead of subprocess strings.

4. For `word_refiner.py`:
   - `build_word_index()`: what it returns and what data it needs from Whisper segments.
   - `snap_to_word_boundary()`: how it adjusts clip `start`/`end` to the nearest word edge using `WORD_END_TAIL_BUFFER`.
   - `refine_all_clips()`: filler-word trimming (`FILLER_WORDS`), stutter detection, `LEADING_CONNECTORS` / `TRAILING_CONNECTORS` guards.
   - `MIN_WORD_DURATION`: why very short words are excluded as alignment noise.

5. Note the SRP boundaries: `ClipAnalyzer` never touches ffmpeg; `VideoCutter` never calls Claude; `word_refiner` never calls either.
