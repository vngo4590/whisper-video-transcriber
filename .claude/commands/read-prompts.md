Read and explain `prompts/clip_prompts.md` — the Claude API prompt templates for viral clip detection.

Steps:
1. Read the file at `prompts/clip_prompts.md`.
2. List each `## SECTION` and summarise what it does in 1–2 sentences.
3. Explain how the sections are loaded at runtime by `_load_prompts()` in `src/clip_analyzer.py` and mapped to each `ClipMode`.
4. Call out any `{placeholders}` in the templates and explain what fills them in at runtime.
5. Note the `{{` / `}}` double-brace convention and why it is required for literal JSON braces inside Python `.format()` templates.
