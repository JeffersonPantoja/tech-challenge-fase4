import csv
from pathlib import Path

from video_review.application.predict_video import PredictionRequest, PredictionResult


class UltralyticsVideoPredictor:
    def predict(self, request: PredictionRequest) -> PredictionResult:
        try:
            import cv2
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("OpenCV/Ultralytics não está instalado. Instale com: .venv/bin/pip install -r requirements.txt") from error

        output_dir = request.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = request.video_path.stem
        output_video = output_dir / f"{stem}-detections.mp4"
        detections_csv = output_dir / f"{stem}-detections.csv"
        if output_video.exists() or detections_csv.exists():
            raise FileExistsError(f"Arquivos de saída já existem em {output_dir}; escolha outra pasta.")

        capture = cv2.VideoCapture(str(request.video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Não foi possível abrir o vídeo: {request.video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        capture.release()
        if fps <= 0:
            raise RuntimeError("Não foi possível obter o FPS do vídeo.")

        model = YOLO(str(request.weights_path))
        writer = None
        frames_processed = 0
        detection_count = 0
        try:
            results = model.predict(
                source=str(request.video_path),
                stream=True,
                conf=request.confidence,
                device=request.device,
                verbose=False,
            )
            with detections_csv.open("w", newline="", encoding="utf-8") as csv_file:
                rows = csv.writer(csv_file)
                rows.writerow(["frame", "timestamp_seconds", "class_id", "class_name", "confidence", "x1", "y1", "x2", "y2"])
                for frame_index, result in enumerate(results):
                    plotted = result.plot()
                    height, width = plotted.shape[:2]
                    if writer is None:
                        writer = cv2.VideoWriter(
                            str(output_video), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
                        )
                        if not writer.isOpened():
                            raise RuntimeError(f"Não foi possível criar o vídeo de saída: {output_video}")
                    writer.write(plotted)
                    frames_processed += 1

                    boxes = result.boxes
                    if boxes is None or len(boxes) == 0:
                        rows.writerow([frame_index, f"{frame_index / fps:.6f}", "", "", "", "", "", "", ""])
                        continue
                    coordinates = boxes.xyxy.cpu().tolist()
                    class_ids = boxes.cls.cpu().tolist()
                    confidences = boxes.conf.cpu().tolist()
                    for coords, class_value, confidence in zip(coordinates, class_ids, confidences):
                        class_id = int(class_value)
                        names = result.names
                        class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else names[class_id]
                        rows.writerow([
                            frame_index,
                            f"{frame_index / fps:.6f}",
                            class_id,
                            class_name,
                            f"{float(confidence):.6f}",
                            *(f"{float(value):.2f}" for value in coords),
                        ])
                        detection_count += 1
        except Exception:
            if writer is not None:
                writer.release()
            output_video.unlink(missing_ok=True)
            detections_csv.unlink(missing_ok=True)
            raise
        finally:
            if writer is not None:
                writer.release()

        if frames_processed == 0:
            detections_csv.unlink(missing_ok=True)
            raise RuntimeError("O modelo não processou nenhum frame do vídeo.")
        return PredictionResult(output_video, detections_csv, frames_processed, detection_count)
