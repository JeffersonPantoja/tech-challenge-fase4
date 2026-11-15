from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TherapyAudioRequest:
    video_path: Path
    output_dir: Path
    aws_region: str = "us-east-1"
    test_duration_seconds: int | None = None


@dataclass(frozen=True)
class TherapyAudioResult:
    audio_path: Path
    transcript_path: Path
    transcript: str
    sentiment: str
    sentiment_scores: dict[str, float]
    aws_region: str
