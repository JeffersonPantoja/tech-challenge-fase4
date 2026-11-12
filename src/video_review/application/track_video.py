from typing import Protocol

from video_review.models import TrackingRequest, TrackingResult

TOOL_CLASSES = (
    "grasper",
    "bipolar",
    "hook",
    "scissors",
    "clipper",
    "irrigator",
    "specimen_bag",
)


class VideoTracker(Protocol):
    def track(self, request: TrackingRequest) -> TrackingResult:
        """Rastreia uma ROI inicial, salvando vídeo e coordenadas por frame."""


class TrackVideo:
    def __init__(self, tracker: VideoTracker) -> None:
        self._tracker = tracker

    def execute(self, request: TrackingRequest) -> TrackingResult:
        if not request.video_path.is_file():
            raise FileNotFoundError(f"Vídeo não encontrado: {request.video_path}")
        if request.tracker_name.upper() not in {"CSRT", "KCF"}:
            raise ValueError("Rastreador inválido. Escolha CSRT ou KCF.")
        if request.tool_class not in TOOL_CLASSES:
            raise ValueError(f"Ferramenta inválida. Escolha uma destas: {', '.join(TOOL_CLASSES)}.")
        if request.video_path.resolve().is_relative_to(request.output_root.resolve()):
            raise ValueError("A pasta de saída não pode conter o vídeo original.")
        return self._tracker.track(request)
