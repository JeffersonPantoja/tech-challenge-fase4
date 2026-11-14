from pathlib import Path

from video_review.application.train_detector import TrainingRequest


class UltralyticsTrainer:
    def train(self, request: TrainingRequest) -> Path:
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("Ultralytics não está instalado. Instale com: .venv/bin/pip install -r requirements.txt") from error

        model = YOLO(request.model)
        try:
            result = model.train(
                data=str(request.dataset_yaml),
                epochs=request.epochs,
                imgsz=request.image_size,
                batch=request.batch_size,
                device=request.device,
                project=str(request.project),
                name=request.name,
                exist_ok=False,
            )
        except Exception as error:
            raise RuntimeError(f"Falha no treinamento Ultralytics: {error}") from error
        save_dir = Path(result.save_dir)
        best_weights = save_dir / "weights" / "best.pt"
        return best_weights
