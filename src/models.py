"""
models.py — Shared configuration constants.

GRASP Information Expert: single authoritative source for app-wide config values.
Changes to window size, model list, or thumbnail dimensions happen only here.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Export format
# ---------------------------------------------------------------------------

class ExportFormat(Enum):
    SRT        = "srt"
    PLAIN_TEXT = "plain_text"


# ---------------------------------------------------------------------------
# Clip aspect ratio
# ---------------------------------------------------------------------------

class AspectRatio(Enum):
    ORIGINAL = "original"   # keep source resolution
    R9_16    = "9:16"       # vertical — TikTok / Reels / Shorts
    R16_9    = "16:9"       # horizontal — YouTube
    R1_1     = "1:1"        # square — Instagram
    R4_3     = "4:3"        # classic

# Target (width, height) per ratio; None means no spatial conversion
ASPECT_RATIO_SIZES: dict[AspectRatio, tuple[int, int] | None] = {
    AspectRatio.ORIGINAL: None,
    AspectRatio.R9_16:    (1080, 1920),
    AspectRatio.R16_9:    (1920, 1080),
    AspectRatio.R1_1:     (1080, 1080),
    AspectRatio.R4_3:     (1440, 1080),
}

ASPECT_RATIO_LABELS: dict[AspectRatio, str] = {
    AspectRatio.ORIGINAL: "Original  (no conversion)",
    AspectRatio.R9_16:    "9:16  vertical  (TikTok / Reels)",
    AspectRatio.R16_9:    "16:9  horizontal  (YouTube)",
    AspectRatio.R1_1:     "1:1  square  (Instagram)",
    AspectRatio.R4_3:     "4:3  classic",
}

DEFAULT_ASPECT_RATIO = AspectRatio.R9_16


# ---------------------------------------------------------------------------
# Analysis strategy
# ---------------------------------------------------------------------------

class AnalysisStrategy(Enum):
    AUDIO_ENERGY  = "audio_energy"    # RMS audio peaks
    VISUAL_MOTION = "visual_motion"   # OpenCV frame differencing
    VISION_MODEL  = "vision_model"    # Claude vision keyframe scoring

ANALYSIS_STRATEGY_LABELS: dict[str, str] = {
    AnalysisStrategy.AUDIO_ENERGY:  "Audio energy  (RMS peaks)",
    AnalysisStrategy.VISUAL_MOTION: "Visual motion  (frame diff)",
    AnalysisStrategy.VISION_MODEL:  "Vision model  (Claude keyframes)",
}

# Default: audio energy only — same behaviour as the previous HIGHLIGHTS-only path.
DEFAULT_ANALYSIS_STRATEGIES: frozenset = frozenset({AnalysisStrategy.AUDIO_ENERGY})


# ---------------------------------------------------------------------------
# Clip mode
# ---------------------------------------------------------------------------

class ClipMode(Enum):
    SINGLE_SHOT = "single_shot"   # one continuous clip per result
    MULTI_CUT   = "multi_cut"     # 2–5 clips merged into one result
    CREATIVE    = "creative"      # AI-directed narrative arc, non-sequential cuts
    REELS       = "reels"         # Instagram Reels: micro-cuts, silence removed, influencer strategies
    HIGHLIGHTS  = "highlights"    # streamer mode: audio energy peaks + Claude selection

CLIP_MODE_LABELS: dict[ClipMode, str] = {
    ClipMode.SINGLE_SHOT: "Single shot  —  one continuous clip",
    ClipMode.MULTI_CUT:   "Multi-cut  —  merged highlight reel",
    ClipMode.CREATIVE:    "Creative edit  —  AI narrative arc",
    ClipMode.REELS:       "Instagram Reels  —  micro-cuts, no silence",
    ClipMode.HIGHLIGHTS:  "Highlights  —  streamer peak moments",
}

DEFAULT_CLIP_MODE = ClipMode.SINGLE_SHOT


# ---------------------------------------------------------------------------
# Clip data models
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """A single contiguous clip window within the source video."""
    start: float   # seconds
    end:   float   # seconds

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class ClipResult:
    """One output clip, which may be assembled from one or more Segments."""

    segments:  list[Segment]
    title:     str
    hook:      str
    reason:    str
    category:  str                    # free-form AI-generated label
    tags:      list[str] = field(default_factory=list)
    description: str = field(default="")
    hashtags:  list[str] = field(default_factory=list)
    narrative: str = field(default="")   # creative mode arc description
    strategy:  str = field(default="")   # reels mode influencer strategy used
    cta_hint:  str = field(default="")   # reels mode suggested caption / CTA
    peak:      str = field(default="")   # highlights mode: description of the peak moment
    output_path: str = field(default="")

    @property
    def start(self) -> float:
        return self.segments[0].start if self.segments else 0.0

    @property
    def end(self) -> float:
        return self.segments[-1].end if self.segments else 0.0

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    @property
    def timestamp_label(self) -> str:
        def fmt(s: float) -> str:
            m, sec = divmod(int(s), 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"
        if len(self.segments) == 1:
            return f"{fmt(self.start)} → {fmt(self.end)}"
        return f"{len(self.segments)} cuts  ·  {fmt(self.start)} – {fmt(self.end)}"


# ---------------------------------------------------------------------------
# Claude model catalogue — ordered cheapest → most expensive
# ---------------------------------------------------------------------------

class ClaudeModel(NamedTuple):
    model_id:  str
    label:     str
    cost_tier: str

CLAUDE_MODELS: list[ClaudeModel] = [
    ClaudeModel("claude-haiku-4-5-20251001", "Haiku 4.5",  "$    fastest & cheapest"),
    ClaudeModel("claude-sonnet-4-6",          "Sonnet 4.6", "$$   balanced  ★ recommended"),
    ClaudeModel("claude-opus-4-6",            "Opus 4.6",   "$$$  most capable"),
]
DEFAULT_CLAUDE_MODEL = CLAUDE_MODELS[1]


# ---------------------------------------------------------------------------
# Whisper
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Word-level editing constants
# ---------------------------------------------------------------------------

FILLER_WORDS: frozenset[str] = frozenset({
    "um", "uh", "umm", "uhh",
    "so", "like", "you know", "basically",
    "anyway", "right", "okay", "ok",
    "literally", "honestly", "actually",
    "i mean", "i guess", "sort of", "kind of",
})

# Words that signal an incomplete thought at the END of a clip.
# Ending a clip on one of these implies a continuation the viewer never hears.
TRAILING_CONNECTORS: frozenset[str] = frozenset({
    "and", "but", "or", "nor", "so", "yet",
    "because", "since", "although", "though", "if", "when",
    "where", "while", "as", "after", "before", "until", "unless",
    "which", "who", "whom", "that",
})

# Words that imply a prior clause at the START of a clip.
# Starting a clip on one of these makes the viewer feel dropped mid-thought.
LEADING_CONNECTORS: frozenset[str] = frozenset({
    "and", "but", "or", "so", "yet",
    "however", "therefore", "thus", "hence",
    "which", "who", "whom",
})

# Seconds of audio tail added after a word-level end snap so the natural
# decay of the final phoneme completes before the hard cut.
WORD_END_TAIL_BUFFER: float = 0.18

# Words shorter than this (seconds) are alignment noise from Whisper and
# should not be used as snap targets or filler candidates.
MIN_WORD_DURATION: float = 0.05


# ---------------------------------------------------------------------------
# Transcription / export
# ---------------------------------------------------------------------------

DEFAULT_EXPORT_FORMAT    = ExportFormat.SRT
DEFAULT_MAX_WORDS_PER_LINE = 5

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
DEFAULT_MODEL  = "base"

THUMBNAIL_SIZE = (180, 180)

DEFAULT_MAX_CLIPS = 5
CLIP_BITRATE      = "8M"
CLIP_FPS          = 30


# ---------------------------------------------------------------------------
# Window / file dialogs
# ---------------------------------------------------------------------------

WINDOW_TITLE = "Whisper Video Transcriber"
WINDOW_SIZE  = "980x640"

SUPPORTED_VIDEO_EXTENSIONS = {".mp4"}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}

MEDIA_FILE_TYPES = [
    ("Media files", "*.mp4 *.mp3 *.wav *.m4a *.flac *.ogg"),
    ("Video files", "*.mp4"),
    ("Audio files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
    ("All files",   "*.*"),
]
