Read and explain `src/transcription/file_handler.py` — the file I/O service.

Steps:
1. Read the file at `src/transcription/file_handler.py`.
2. Describe `FileHandler.save_transcription()`: inputs, output file naming convention (`_transcription.srt` / `_transcription.txt`), and return value.
3. Explain why file I/O is isolated here (SRP) instead of living in the controller or transcription service.
4. Suggest how this class could be extended (e.g. saving to a custom path, emitting both SRT and TXT at once) without changing `TranscriptionController`.
