Read and explain the transcription package: `src/transcription/`.

Steps:
1. Read all five files:
   - `src/transcription/service.py`
   - `src/transcription/file_handler.py`
   - `src/transcription/_srt_utils.py`
   - `src/transcription/ocr_extractor.py`
   - `src/transcription/merger.py`

2. For `service.py` / `TranscriptionService`:
   - All parameters of `transcribe()`, including the new `extract_onscreen` and `on_log` arguments.
   - The two code paths: speech-only (`_build_srt` / plain text) vs. the OCR path (`_transcribe_with_onscreen`).
   - Why `OcrExtractor` and `TranscriptMerger` are imported inside `_transcribe_with_onscreen` (deferred import — easyocr not required unless the feature is enabled).
   - SOLID principles: SRP, OCP (subclass to swap ASR backend), DIP.

3. For `_srt_utils.py`:
   - Why these helpers were extracted from `service.py` into their own module.
   - `format_srt_timestamp()`, `format_plain_timestamp()`, `split_segment()` — inputs, outputs, the DTW word-timestamp vs. equal-duration fallback.

4. For `ocr_extractor.py` / `OcrExtractor`:
   - `OcrEntry` dataclass fields and meaning.
   - `extract()`: OpenCV frame sampling, EasyOCR, confidence threshold, min-text-length filter, `on_log` progress reporting.
   - `_merge_consecutive()`: normalisation, deduplication of frames showing the same text, how `end` time is computed.
   - The lazy-init pattern for the EasyOCR reader and why `gpu=False` is the safe default.

5. For `merger.py` / `TranscriptMerger`:
   - `merge_to_srt()`: how speech segments (split via `split_segment`) and OCR entries are combined, sorted, and labelled `[SPEECH]` / `[ON-SCREEN]`.
   - `merge_to_plain()`: the `[SPEECH @ HH:MM:SS]` / `[ON-SCREEN @ HH:MM:SS]` line format.
   - Tie-breaking sort key (speech before on-screen at equal timestamps).
