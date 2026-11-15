"""OpenCV, Ultralytics e OpenAI adapters para o relatório de primeira detecção."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Iterator

from video_review.application.first_tool_report import ConfirmedDetection, ToolDetection


class OpenCvFrameSource:
    def frames(
        self, video_path: Path, start_seconds: float, end_seconds: float | None
    ) -> Iterator[tuple[int, float, object]]:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError("OpenCV não está instalado. Instale as dependências de requirements.txt.") from error

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Não foi possível abrir o vídeo: {video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or total_frames <= 0:
            capture.release()
            raise RuntimeError("Não foi possível obter FPS e duração válidos do vídeo.")

        start_frame = int(start_seconds * fps)
        end_frame = min(total_frames, int(end_seconds * fps)) if end_seconds is not None else total_frames
        if start_frame >= total_frames:
            capture.release()
            raise ValueError(f"O início ({start_seconds}s) está além da duração do vídeo ({total_frames / fps:.3f}s).")
        if end_frame <= start_frame:
            capture.release()
            raise ValueError("O intervalo solicitado não contém frames do vídeo.")

        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        try:
            for frame_index in range(start_frame, end_frame):
                ok, frame = capture.read()
                if not ok:
                    break
                yield frame_index, fps, frame
        finally:
            capture.release()


class UltralyticsFrameDetector:
    def __init__(self, weights_path: Path) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError("Ultralytics não está instalado. Instale as dependências de requirements.txt.") from error
        self._model = YOLO(str(weights_path))

    def detect(self, frame: object, confidence: float, device: str | None) -> list[ToolDetection]:
        results = self._model.predict(
            source=frame,
            conf=confidence,
            device=device,
            verbose=False,
        )
        if not results or results[0].boxes is None:
            return []
        result = results[0]
        boxes = result.boxes
        coordinates = boxes.xyxy.cpu().tolist()
        class_ids = boxes.cls.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        names = result.names
        detections = []
        for box, class_value, score in zip(coordinates, class_ids, confidences):
            class_id = int(class_value)
            class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else names[class_id]
            detections.append(
                ToolDetection(
                    class_id=class_id,
                    class_name=str(class_name),
                    confidence=float(score),
                    box_xyxy=tuple(float(value) for value in box),
                )
            )
        return detections


class OpenAIVisionAnalyzer:
    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Defina OPENAI_API_KEY no ambiente para habilitar o envio do frame à OpenAI.")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("O SDK OpenAI não está instalado. Instale as dependências de requirements.txt.") from error
        self._client = OpenAI(api_key=api_key)

    def describe(
        self,
        frame: object,
        detections: tuple[ConfirmedDetection, ...],
        model: str,
    ) -> str:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError("OpenCV é necessário para codificar o frame enviado à OpenAI.") from error

        height, width = frame.shape[:2]
        scale = min(1.0, 1536 / max(height, width))
        if scale < 1.0:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        encoded_ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not encoded_ok:
            raise RuntimeError("Não foi possível codificar o frame para análise visual.")
        image_url = "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")
        detection_text = "; ".join(
            f"{item.detection.class_name} (previsão YOLO, confiança {item.detection.confidence:.3f}, "
            f"caixa {tuple(round(value, 1) for value in item.detection.box_xyxy)})"
            for item in detections
        )
        prompt = (
            "Descreva objetivamente apenas elementos visíveis neste frame de vídeo cirúrgico para um relatório "
            "técnico de revisão humana. O detector local produziu estas previsões não verificadas: "
            f"{detection_text}. Não confirme nem corrija a classe do detector; não infira diagnóstico, "
            "anomalia clínica, intenção, condição do paciente ou recomendação/procedimento. Informe quando "
            "a imagem não permitir uma observação segura e distinga observações visuais de metadados fornecidos."
        )
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}},
                        ],
                    }
                ],
                max_tokens=500,
                temperature=0.2,
            )
        except Exception as error:
            raise RuntimeError(f"Falha na solicitação à OpenAI ({type(error).__name__}).") from error
        description = response.choices[0].message.content
        if not description:
            raise RuntimeError("A OpenAI API retornou uma descrição vazia.")
        return description.strip()
