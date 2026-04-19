Read and explain the Claude API prompt templates used in this project.

Steps:
1. Read both prompt files: `prompts/clip_prompts.md` and `prompts/content_plan_prompts.md`.

2. For `clip_prompts.md`:
   - List each `## SECTION` and summarise what it does in 1–2 sentences.
   - Explain how sections are loaded by `_load_prompts()` in `src/clips/analyzer.py` and mapped to each `ClipMode` via `_TEMPLATES`.
   - Call out every `{placeholder}` and what fills it at runtime (`max_clips`, `transcript`, `editing_rules`, etc.).
   - Note the `{{` / `}}` double-brace convention for literal JSON braces inside `.format()` templates.

3. For `content_plan_prompts.md`:
   - Same section-by-section walkthrough.
   - Explain how `generate_plan()` in `src/analysis/content_planner.py` loads and fills the template.
   - Describe the `{focus}`, `{max_highlights}`, `{context_block}`, `{transcript}` placeholders.

4. Explain how `custom_instructions` and `prompt_override` in `ClipAnalyzer.find_viral_moments()` interact with the loaded templates — when they append vs. replace the base template.
