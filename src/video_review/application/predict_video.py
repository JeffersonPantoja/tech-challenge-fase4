from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PredictionRequest:
    video_path: Path
    weights_path: Path
    output_dir: Path
    confidence: float = 0.25
    device: str | None = None


@dataclass(frozen=True)
class PredictionResult:
    output_video: Path
    detections_csv: Path
    frames_processed: int
    detection_count: int


class VideoPredictor(Protocol):
    def predict(self, request: PredictionRequest) -> PredictionResult: ...


class PredictVideo:
    def __init__(self, predictor: VideoPredictor) -> None:
        self._predictor = predictor

    def execute(self, request: PredictionRequest) -> PredictionResult:
        if not request.video_path.is_file():
            raise FileNotFoundError(f"Vídeo não encontrado: {request.video_path}")
        if not request.weights_path.is_file():
            raise FileNotFoundError(f"Pesos do modelo não encontrados: {request.weights_path}")
        if not 0 < request.confidence <= 1:
            raise ValueError("A confiança deve estar no intervalo (0, 1].")
        return self._predictor.predict(request)
