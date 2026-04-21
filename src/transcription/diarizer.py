"""
transcription/diarizer.py — Speaker diarization via pyannote.audio.

Lazy-imports pyannote so the app stays importable without it installed.
Call `is_available()` to check at startup without triggering the heavy import.
"""
from dataclasses import dataclass


@dataclass
class DiarizationSegment:
    start: float
    end: float
    speaker: str  # raw pyannote label, e.g. "SPEAKER_00"


def is_available() -> bool:
    """Return True if pyannote.audio is importable (model not yet loaded)."""
    import importlib.util
    return importlib.util.find_spec("pyannote") is not None


def label_to_display(speaker: str) -> str:
    """
    Convert a raw pyannote speaker ID to a human-readable label.

    ``"SPEAKER_00"`` → ``"Speaker A"``
    ``"SPEAKER_01"`` → ``"Speaker B"``
    """
    if not speaker:
        return ""
    try:
        index = int(speaker.split("_")[-1])
        return f"Speaker {chr(ord('A') + index)}"
    except (ValueError, IndexError):
        return speaker


class SpeakerDiarizer:
    """
    Runs pyannote.audio speaker diarization on a media file.

    Requires pyannote.audio and a Hugging Face access token with
    access to the gated pyannote/speaker-diarization-3.1 model.
    """

    _MODEL = "pyannote/speaker-diarization-3.1"

    def diarize(
        self,
        path: str,
        hf_token: str,
        on_log=None,
    ) -> list[DiarizationSegment]:
        """
        Run diarization on *path* and return one segment per speaker turn.

        Args:
            path:     Absolute path to the audio/video file.
            hf_token: Hugging Face user-access token for gated model access.
            on_log:   Optional ``(message, level)`` logging callback.

        Returns:
            List of DiarizationSegment sorted by start time.

        Raises:
            ImportError:  if pyannote.audio is not installed.
            RuntimeError: if the HF token is invalid or model access is denied.
        """
        def _log(msg: str, level: str = "detail") -> None:
            if on_log:
                on_log(msg, level)

        try:
            import torchaudio
            # torchaudio 2.x removed list_audio_backends; pyannote.audio 3.x still calls it
            if not hasattr(torchaudio, "list_audio_backends"):
                torchaudio.list_audio_backends = lambda: ["soundfile"]
        except ImportError as exc:
            raise ImportError(
                "Speaker diarization requires torchaudio.\n"
                "Install it with: pip install torchaudio"
            ) from exc

        import huggingface_hub as _hf
        for _fn_name in ("hf_hub_download", "snapshot_download"):
            _fn = getattr(_hf, _fn_name, None)
            if _fn and "use_auth_token" not in _fn.__code__.co_varnames:
                def _make_patched(original):
                    def _patched(*args, **kwargs):
                        if "use_auth_token" in kwargs:
                            kwargs.setdefault("token", kwargs.pop("use_auth_token"))
                        return original(*args, **kwargs)
                    return _patched
                setattr(_hf, _fn_name, _make_patched(_fn))

        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise ImportError(
                "Speaker diarization requires pyannote.audio.\n"
                "Install it with: pip install pyannote.audio"
            ) from exc

        _log(f"Loading diarization model ({self._MODEL})…", "detail")
        pipeline = Pipeline.from_pretrained(self._MODEL, use_auth_token=hf_token)

        _log("Loading audio…", "detail")
        waveform, sample_rate = torchaudio.load(path)
        audio = {"waveform": waveform, "sample_rate": sample_rate}

        _log("Running speaker diarization…", "detail")
        diarization = pipeline(audio)

        segments: list[DiarizationSegment] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(DiarizationSegment(
                start=turn.start,
                end=turn.end,
                speaker=speaker,
            ))

        unique_speakers = sorted({s.speaker for s in segments})
        _log(
            f"Diarization complete — {len(unique_speakers)} speaker(s): "
            + ", ".join(label_to_display(s) for s in unique_speakers),
            "detail",
        )

        return sorted(segments, key=lambda s: s.start)


def assign_speakers(
    whisper_segments: list[dict],
    diarization: list[DiarizationSegment],
) -> list[dict]:
    """
    Annotate each Whisper segment with the dominant speaker label.

    For each segment, finds the diarization window with the greatest time
    overlap and stores its raw label under the ``"speaker"`` key.  Segments
    with no diarization overlap receive an empty string.

    Modifies *whisper_segments* in-place and also returns the list.
    """
    for seg in whisper_segments:
        seg_start = seg["start"]
        seg_end   = seg["end"]
        best_speaker = ""
        best_overlap = 0.0

        for d in diarization:
            overlap = min(seg_end, d.end) - max(seg_start, d.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d.speaker

        seg["speaker"] = best_speaker

    return whisper_segments
