"""
transcription/diarizer.py — Speaker diarization using torchaudio + scipy.

Identifies speaker turns via MFCC feature extraction and agglomerative
clustering. No pyannote.audio, no Hugging Face token, no torchcodec required.
Works on CPU with torchaudio 2.x.
"""
from dataclasses import dataclass


@dataclass
class DiarizationSegment:
    start: float
    end: float
    speaker: str  # raw label, e.g. "SPEAKER_00"

    @property
    def duration(self) -> float:
        return self.end - self.start


def is_available() -> bool:
    """Return True if diarization dependencies are importable."""
    import importlib.util
    return all(
        importlib.util.find_spec(pkg) is not None
        for pkg in ("torchaudio", "scipy", "numpy")
    )


def label_to_display(speaker: str) -> str:
    """Convert SPEAKER_00 → 'Speaker A', SPEAKER_01 → 'Speaker B', etc."""
    if not speaker:
        return ""
    try:
        index = int(speaker.split("_")[-1])
        return f"Speaker {chr(ord('A') + index)}"
    except (ValueError, IndexError):
        return speaker


class SpeakerDiarizer:
    """
    Speaker diarization via MFCC feature extraction + agglomerative clustering.

    Algorithm:
      1. Load audio, convert to mono, resample to 16 kHz.
      2. Compute 40-coefficient MFCCs.
      3. Slice into overlapping 1.5 s windows; each window → mean+std feature vector.
      4. Z-score normalise features.
      5. Ward-linkage agglomerative clustering on cosine distances.
      6. Smooth labels with a median filter; merge short segments.
    """

    _TARGET_SR  = 16_000
    _N_MFCC     = 40
    _HOP_LENGTH = 160       # ~10 ms per frame at 16 kHz
    _WIN_S      = 1.5       # window length (seconds)
    _HOP_S      = 0.75      # hop between windows (seconds)
    _THRESHOLD  = 0.5       # cosine distance threshold for auto cluster count
    _MIN_SEG_S  = 0.5       # minimum output segment duration (seconds)

    def diarize(
        self,
        path: str,
        num_speakers: int = 0,
        on_log=None,
    ) -> list[DiarizationSegment]:
        """
        Run diarization on *path* and return one segment per speaker turn.

        Args:
            path:         Absolute path to the audio/video file.
            num_speakers: Expected number of speakers. 0 = auto-detect.
            on_log:       Optional ``(message, level)`` logging callback.

        Returns:
            List of DiarizationSegment sorted by start time.

        Raises:
            ImportError: if torchaudio or scipy is not installed.
        """
        def _log(msg: str, level: str = "detail") -> None:
            if on_log:
                on_log(msg, level)

        import numpy as np
        import torchaudio
        import torchaudio.transforms as T
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.ndimage import median_filter
        from scipy.spatial.distance import pdist

        # ── 1. Load audio ─────────────────────────────────────────────────
        _log("Loading audio for diarization…")
        waveform, sr = torchaudio.load(path)

        if waveform.shape[0] > 1:
            waveform = waveform.mean(0, keepdim=True)

        if sr != self._TARGET_SR:
            waveform = torchaudio.functional.resample(waveform, sr, self._TARGET_SR)
            sr = self._TARGET_SR

        total_dur = waveform.shape[1] / sr

        # ── 2. MFCC extraction ────────────────────────────────────────────
        _log(f"Audio: {total_dur:.1f}s  |  Extracting speaker features…")
        mfcc_fn = T.MFCC(
            sample_rate=sr,
            n_mfcc=self._N_MFCC,
            melkwargs={
                "n_fft": 512,
                "hop_length": self._HOP_LENGTH,
                "n_mels": 80,
                "f_min": 20.0,
            },
        )
        mfcc = mfcc_fn(waveform).squeeze(0).numpy()  # (n_mfcc, T)

        # ── 3. Sliding-window feature vectors (mean + std per window) ─────
        fps     = sr / self._HOP_LENGTH
        win_f   = int(self._WIN_S * fps)
        hop_f   = int(self._HOP_S * fps)
        T_total = mfcc.shape[1]

        vectors: list[np.ndarray] = []
        times:   list[tuple[float, float]] = []
        t = 0
        while t + win_f <= T_total:
            chunk = mfcc[:, t:t + win_f]
            vectors.append(np.concatenate([chunk.mean(1), chunk.std(1)]))  # 80-dim
            times.append((t / fps, (t + win_f) / fps))
            t += hop_f

        if len(vectors) < 2:
            return [DiarizationSegment(0.0, total_dur, "SPEAKER_00")]

        # ── 4. Normalise ──────────────────────────────────────────────────
        X = np.array(vectors)
        X = (X - X.mean(0)) / (X.std(0) + 1e-8)

        # ── 5. Agglomerative clustering ───────────────────────────────────
        _log("Clustering speakers…")
        D = pdist(X, metric="cosine")
        Z = linkage(D, method="ward")

        if num_speakers and num_speakers > 1:
            labels = fcluster(Z, t=num_speakers, criterion="maxclust")
        else:
            labels = fcluster(Z, t=self._THRESHOLD, criterion="distance")

        # Smooth single-window jitter with a small median filter
        labels = median_filter(labels.astype(float), size=3).astype(int)

        # ── 6. Build and post-process segments ────────────────────────────
        segs: list[DiarizationSegment] = []
        prev      = labels[0]
        seg_start = times[0][0]

        for i, lbl in enumerate(labels[1:], 1):
            if lbl != prev:
                segs.append(DiarizationSegment(seg_start, times[i][0], f"SPEAKER_{prev - 1:02d}"))
                seg_start = times[i][0]
                prev = lbl

        segs.append(DiarizationSegment(seg_start, total_dur, f"SPEAKER_{prev - 1:02d}"))
        segs = _merge_short_segments(segs, self._MIN_SEG_S)

        unique = sorted({s.speaker for s in segs})
        _log(
            f"Diarization complete — {len(unique)} speaker(s): "
            + ", ".join(label_to_display(s) for s in unique),
        )
        return sorted(segs, key=lambda s: s.start)


def _merge_short_segments(
    segs: list[DiarizationSegment],
    min_dur: float,
) -> list[DiarizationSegment]:
    """Absorb segments shorter than *min_dur* into the longer adjacent neighbour."""
    if len(segs) < 2:
        return segs
    result = list(segs)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(result):
            if result[i].duration >= min_dur or len(result) == 1:
                i += 1
                continue
            has_prev = i > 0
            has_next = i < len(result) - 1
            if has_prev and (not has_next or result[i - 1].duration >= result[i + 1].duration):
                result[i - 1] = DiarizationSegment(
                    result[i - 1].start, result[i].end, result[i - 1].speaker
                )
            else:
                result[i + 1] = DiarizationSegment(
                    result[i].start, result[i + 1].end, result[i + 1].speaker
                )
            result.pop(i)
            changed = True
    return result


def assign_speakers(
    whisper_segments: list[dict],
    diarization: list[DiarizationSegment],
) -> list[dict]:
    """
    Annotate each Whisper segment with the dominant speaker label.

    Finds the diarization window with the greatest time overlap and stores
    its raw label under the ``"speaker"`` key. Modifies *whisper_segments*
    in-place and also returns the list.
    """
    for seg in whisper_segments:
        seg_start    = seg["start"]
        seg_end      = seg["end"]
        best_speaker = ""
        best_overlap = 0.0

        for d in diarization:
            overlap = min(seg_end, d.end) - max(seg_start, d.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d.speaker

        seg["speaker"] = best_speaker

    return whisper_segments
