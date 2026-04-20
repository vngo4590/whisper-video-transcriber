Read and explain the Claude API prompt templates used in this project.

Prompt files are split into focused single-purpose files grouped by feature folder.
The old monolithic `*_prompts.md` files no longer exist — do not reference them.

Steps:
1. Read all prompt files across the three folders:
   - `prompts/clips/system.md`, `prompts/clips/editing_rules.md`
   - `prompts/clips/single_shot.md`, `prompts/clips/multi_cut.md`,
     `prompts/clips/creative.md`, `prompts/clips/reels.md`, `prompts/clips/highlights.md`
   - `prompts/chapters/system.md`, `prompts/chapters/user_template.md`
   - `prompts/content_plan/system.md`, `prompts/content_plan/user_template.md`

2. For `prompts/clips/`:
   - `system.md` — shared system prompt sent with every clip request; list its absolute rules and output quality rules.
   - `editing_rules.md` — mandatory editing block injected via `{editing_rules}` into every mode template; summarise each bullet.
   - For each of the five mode templates (`single_shot`, `multi_cut`, `creative`, `reels`, `highlights`):
     - State the mode objective in one sentence.
     - List every `{placeholder}` and what fills it at runtime (`max_clips`, `transcript`, `editing_rules`).
     - Note any mode-specific rules or strategy fields unique to that template.
   - Explain how `_p("filename.md")` in `src/clips/analyzer.py` reads each file and how `_TEMPLATES` maps `ClipMode` → template string.
   - Note the `{{` / `}}` double-brace convention for literal JSON braces inside `.format()` templates.

3. For `prompts/content_plan/`:
   - `system.md` — the 5-pillar evaluation framework; name each pillar.
   - `user_template.md` — placeholders: `{focus}`, `{max_highlights}`, `{context_block}`, `{transcript}`; describe the JSON output schema fields.
   - Explain how `_p()` in `src/analysis/content_planner.py` loads these and how `generate_plan()` fills and sends them.

4. For `prompts/chapters/`:
   - `system.md` — chapter segmentation rules (coverage, min duration, boundary constraints).
   - `user_template.md` — placeholders: `{max_chapters}`, `{transcript}`; JSON output schema.
   - Explain how `_p()` in `src/analysis/chapters.py` loads these and how `generate_chapters()` fills them.

5. Explain how `custom_instructions` and `prompt_override` in `ClipAnalyzer.find_viral_moments()` interact with the loaded templates — when they append vs. replace the base template, and where `_build_constraints()` injects clip duration and cuts-per-clip limits.
