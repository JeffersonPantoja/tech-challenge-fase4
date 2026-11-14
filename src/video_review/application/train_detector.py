from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TrainingRequest:
    dataset_yaml: Path
    model: str
    epochs: int
    image_size: int
    batch_size: int
    device: str | None
    project: Path
    name: str


class DetectorTrainer(Protocol):
    def train(self, request: TrainingRequest) -> Path: ...


class TrainDetector:
    def __init__(self, trainer: DetectorTrainer) -> None:
        self._trainer = trainer

    def execute(self, request: TrainingRequest) -> Path:
        if not request.dataset_yaml.is_file():
            raise FileNotFoundError(f"data.yaml não encontrado: {request.dataset_yaml}")
        if request.epochs <= 0 or request.image_size <= 0 or request.batch_size <= 0:
            raise ValueError("Épocas, tamanho de imagem e batch devem ser positivos.")
        return self._trainer.train(request)
