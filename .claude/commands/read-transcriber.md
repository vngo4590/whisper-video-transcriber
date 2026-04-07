Read and explain `src/transcriber.py` — the Whisper transcription service.

Steps:
1. Read the file at `src/transcriber.py`.
2. Describe `TranscriptionService.transcribe()`: its parameters, return value, and the two output modes (plain text vs timestamped).
3. Explain `_build_timestamped_text()` and `_format_timestamp()`.
4. Note the SOLID principles that shaped this module (SRP, OCP, DIP).
5. Identify what the caller must supply and what this module never touches (UI, file I/O).
