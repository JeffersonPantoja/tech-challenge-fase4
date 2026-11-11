from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrackingRequest:
    video_path: Path
    output_path: Path
    tracker_name: str = "CSRT"
    display: bool = True


@dataclass(frozen=True)
class TrackingResult:
    video_path: Path
    output_path: Path
    annotations_path: Path
    tracker_name: str
    frames_processed: int
    tracking_failures: int
    stopped_by_user: bool
