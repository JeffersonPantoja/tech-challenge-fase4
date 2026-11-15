from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TherapyAudioRequest:
    video_path: Path
    output_dir: Path
    aws_region: str = "us-east-1"
    test_duration_seconds: int | None = None
    start_seconds: int = 0


@dataclass(frozen=True)
class TranscriptSegment:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class SegmentSentiment:
    segment: TranscriptSegment
    sentiment: str
    sentiment_scores: dict[str, float]


@dataclass(frozen=True)
class TherapyAudioResult:
    audio_path: Path
    transcript_path: Path
    transcript: str
    segment_sentiments: list[SegmentSentiment]
    aws_region: str
