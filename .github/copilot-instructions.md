# Copilot instructions — Whisper Video Transcriber

Tkinter desktop app (Python 3.14, Windows-first) that transcribes media with Whisper and uses the
Anthropic Claude API to generate viral clips, content plans, and chapters.

## Commands

```powershell
.\.venv\Scripts\Activate.ps1          # venv lives at .venv (gitignored)
pip install -r requirements.txt
python main.py                        # run the GUI
```

There is **no test suite, linter, or build script**. Do not add one unless asked. Verify changes with:

```powershell
python -m compileall src main.py      # syntax check everything
python -c "import src.ui.app"         # import-graph / circular-import check
python -c "import src.clips.analyzer" # prompt files load at import time — catches missing prompts/*.md
```

External requirements: **FFmpeg on PATH** (clip cutting, caption burn-in), an Anthropic API key
(entered in the UI, persisted via `src/config/settings.py`), and optionally `pyannote.audio` +
a Hugging Face token for speaker diarization (commented out in `requirements.txt`).

## Architecture

Strict four-layer split; imports only ever point downward:

```
main.py → src/ui/app.py (App) → src/controllers/* → src/{transcription,clips,analysis,media}/* → src/models.py
```

- **`src/ui/app.py` — the only wiring point.** `App` constructs every service and controller, owns
  the `ttk.Notebook` (Transcript / Clips / Content Plan / Chapters / Activity) and the sidebar, and
  routes controller callbacks back to the right panel. New features are wired here.
- **`src/controllers/*`** own the workflows (transcription, clips, content plan). Each has a
  `run(...)` that returns immediately after spawning a `daemon=True` thread, plus a private
  `_worker`. Controllers own **no widgets** and never import tkinter.
- **Domain packages** (`transcription`, `clips`, `analysis`, `media`) are pure logic: no tkinter,
  no callbacks into the UI beyond the optional `on_log`/`on_stage` hooks.
- **`src/models.py`** is the single source of truth for enums (`ClipMode`, `AspectRatio`,
  `AnalysisStrategy`, `ExportFormat`), dataclasses (`Segment`, `ClipResult`), the Claude model
  catalogue, and app-wide constants. Add constants here, not inline.

Chapters are the exception: `App._chapters_worker` calls `src/analysis/chapters.py` directly
instead of going through a controller.

## Conventions that aren't obvious from one file

**Threading / UI marshalling.** Workers run on background threads and must never touch widgets.
Every result crosses back via `self._root.after(0, lambda: ...)` in `App`. `ActivityLogPanel.append`
does its own `root.after(0, …)` marshalling, so `on_log` may be called directly from a worker.

**Cancellation is cooperative.** One `threading.Event` (`App._cancel_event`) is shared by all
controllers and passed into every `run(...)`. Cancel/`Escape` calls `.set()`; workers call
`self._check_cancel(cancel_event)` **between** stages, which raises `OperationCancelledError`
(`src/controllers/__init__.py`). Long calls (Whisper, ffmpeg, Claude) finish first so nothing is
left half-written. Workers catch `OperationCancelledError` → `on_error("Operation was cancelled.")`,
catch `Exception` → `on_error(str(exc))`, and always call `on_done()` in `finally`.

**Callback contract.** Controllers communicate only through injected callables named
`on_start` / `on_stage` / `on_success` / `on_error` / `on_done` / `on_log` (plus per-item hooks like
`on_clip_done`). Keep new work in that shape rather than returning values or importing UI code.

**Stage strings are numbered.** Every `on_stage` message is prefixed `"Step N/M — …"` so the
sidebar shows pipeline position. Compute `total` up front from the enabled options.

**Activity log levels.** `on_log(message, level)` where level ∈
`stage | api | detail | success | warn | error | info` (colours in `_LEVEL_COLOURS`,
`src/ui/panels/activity_log.py`). Unknown levels silently fall back to `info`.

**Prompts live in `prompts/`, not in Python.** `src/clips/analyzer.py`, `src/analysis/chapters.py`,
and `src/analysis/content_planner.py` each define a `_p(name)` loader that reads
`prompts/<area>/<file>.md` at **module import time**. Tune Claude behaviour by editing the markdown;
adding a new `ClipMode` means adding both an enum member in `models.py` and a template file
registered in `analyzer._TEMPLATES`. Renaming or deleting a prompt file breaks imports.

**Settings are a module, not a class.** `from src.config import settings` then
`settings.get(key, default)` / `settings.save(**kwargs)` / `settings.get_recent_files()`. Writes are
best-effort and never raise. Never hardcode or commit an API key.

**Panel API.** Right-panel classes expose the same small surface — `reset()`, `set_stage(text)`,
`show_loading(bool)`, and a setter (`set_text`, `add_clip`, `set_chapters`). Follow it when adding
a tab; register the tab in `App._build_layout` and select it by index in the success callback.

**Style.** Module docstrings state the file's single responsibility and the SOLID/GRASP role it
plays — keep that header format. Files are kept small (~200 lines soft limit; split rather than
grow). Optional/graceful-degradation imports use `try: … except ImportError:` with a fallback
(see `tkinterdnd2` in `src/ui/app.py`).

## Workflow tooling

`openspec/` holds a spec-driven change workflow (`openspec/changes/`, `openspec/specs/`) driven by
the `openspec` CLI. The matching skills are not currently installed in this repo.

`.github/skills/read-*/SKILL.md` are curated read-lists per subsystem (`read-controller`,
`read-clips`, `read-ui`, `read-transcriber`, …) — use them to find the relevant files for a
subsystem quickly instead of scanning `src/`. `.github/agents/` holds the project's custom agents.
