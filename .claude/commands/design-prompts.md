Design, improve, or add prompt templates for the AI analysis features in this project.

This skill covers both prompt files and the analysis options wired to them:
- `prompts/clip_prompts.md` — clip extraction templates used by `src/clips/analyzer.py`
- `prompts/content_plan_prompts.md` — content plan templates used by `src/analysis/content_planner.py`
- `src/analysis/content_planner.py` — `FOCUS_OPTIONS` list shown in the Content Plan UI tab

---

## When to use this skill

- Adding a new clip mode template (e.g. a new `ClipMode` value like `DOCUMENTARY`)
- Improving an existing template (better JSON schema, new fields, tighter instructions)
- Adding a new focus option to the Content Plan tab
- Debugging why Claude is returning bad JSON or wrong timestamps
- Tuning the system prompt to handle a new content type (cooking, corporate, lecture, etc.)

---

## Steps

### 1. Read the current state

Read both prompt files and the analyzer to understand what exists:
- `prompts/clip_prompts.md` — all `## SECTION` blocks
- `prompts/content_plan_prompts.md` — `## SYSTEM_PROMPT` and `## USER_TEMPLATE`
- `src/clips/analyzer.py` — how `_load_prompts()` maps sections to `ClipMode` via `_TEMPLATES`
- `src/analysis/content_planner.py` — `FOCUS_OPTIONS` list and `generate_plan()` parameters
- `src/models.py` — `ClipMode` enum values

### 2. Understand the constraints

**Section names are load-time contracts.** The Python code reads sections by exact `## HEADING`:
- `SYSTEM_PROMPT`, `EDITING_RULES` — always loaded
- `SINGLE_SHOT_TEMPLATE`, `MULTI_CUT_TEMPLATE`, `CREATIVE_TEMPLATE`, `REELS_TEMPLATE`, `HIGHLIGHTS_TEMPLATE` — one per `ClipMode`

Adding a **new** clip mode requires:
1. A new `ClipMode` value in `src/models.py`
2. A `CLIP_MODE_LABELS` entry
3. A new `## NEW_MODE_TEMPLATE` section in `clip_prompts.md`
4. An entry in `_TEMPLATES` in `src/clips/analyzer.py`
5. Optionally a new radio button in `src/ui/sidebar/tabs/video_clips.py`

**Double-brace rule.** Literal `{` and `}` characters in the JSON output schema must be escaped as `{{` and `}}` because the templates are filled with Python `.format()`. Single `{placeholder}` braces are runtime substitution points — do not escape them.

**Available placeholders:**
- Clip templates: `{max_clips}`, `{transcript}`, `{editing_rules}`
- Content plan template: `{focus}`, `{max_highlights}`, `{context_block}`, `{transcript}`

### 3. Design principles to follow

When writing or editing prompt sections:

**Be specific about output format.** Claude must return exactly one JSON object. State "Return ONLY this exact JSON shape" and show the full schema with every field. Ambiguous output instructions cause pipeline failures.

**Layer the rules.** The `SYSTEM_PROMPT` sets absolute rules. `EDITING_RULES` repeats the most critical ones for per-template reinforcement. Mode-specific templates add rules on top. Don't repeat absolute rules verbatim in templates — say "(on top of the absolute rules)".

**Use real examples in rule explanations.** "Never open on filler" is weaker than "Never open on 'um', 'uh', 'so', 'like', 'you know'." Concrete beats abstract for language model instruction.

**Timestamp discipline.** Every template must remind Claude that start/end times must match exact values from the transcript. This is the most common failure mode — repeat it clearly.

**Content-type honesty.** Don't frame all content as "viral social media." Templates should reflect the actual source material. A lecture clip and a cooking demo clip need different framing, different category labels, and different quality signals.

**Category labels matter.** The `category` field in clip JSON is surfaced in the UI. Use labels that describe the content, not just the emotion: `tutorial`, `demonstration`, `recipe`, `debate`, `story`, `insight` are more actionable than `educational` or `emotional`.

### 4. Adding a new FOCUS_OPTIONS entry

Edit `src/analysis/content_planner.py`:
```python
FOCUS_OPTIONS: list[str] = [
    "All highlights",
    "Key insights & takeaways",
    ...
    "Your new focus option here",   # ← add here
    "Custom",                        # always keep Custom last
]
```
The string is passed verbatim as `{focus}` into the `USER_TEMPLATE`. Make it descriptive enough for Claude to understand the intent without needing extra instructions.

### 5. Testing a prompt change

After editing a template, verify:
1. All `{placeholders}` are still present and spelled correctly
2. All literal JSON braces are doubled: `{{` and `}}`
3. The section heading (`## HEADING`) is unchanged — Python matches by exact string
4. The JSON schema is complete — every field Claude needs to return is shown
5. Run a real transcription through the affected mode and check the raw response for JSON validity
