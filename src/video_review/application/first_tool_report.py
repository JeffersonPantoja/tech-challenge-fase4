"""Seleciona a primeira detecção estável e monta relatório técnico."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterator, Protocol


@dataclass(frozen=True)
class ToolDetection:
    class_id: int
    class_name: str
    confidence: float
    box_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class ConfirmedDetection:
    detection: ToolDetection
    consecutive_frames: int


@dataclass(frozen=True)
class FirstToolReportRequest:
    video_path: Path
    weights_path: Path
    output_dir: Path
    start_seconds: float = 0.0
    end_seconds: float | None = None
    confidence: float = 0.25
    consecutive_frames: int = 3
    device: str | None = None
    send_frame_to_openai: bool = False
    openai_model: str = "gpt-4o"


@dataclass(frozen=True)
class FirstToolReportResult:
    frame_path: Path
    json_path: Path
    markdown_path: Path
    frame_index: int
    timestamp_seconds: float
    detections: tuple[ConfirmedDetection, ...]
    vision_description: str | None
    confirmation_frame_index: int


class FrameSource(Protocol):
    def frames(
        self, video_path: Path, start_seconds: float, end_seconds: float | None
    ) -> Iterator[tuple[int, float, object]]: ...


class FrameDetector(Protocol):
    def detect(
        self, frame: object, confidence: float, device: str | None
    ) -> list[ToolDetection]: ...


class VisionAnalyzer(Protocol):
    def describe(
        self,
        frame: object,
        detections: tuple[ConfirmedDetection, ...],
        model: str,
    ) -> str: ...


class FirstToolReport:
    def __init__(
        self,
        frame_source: FrameSource,
        detector: FrameDetector,
        vision_analyzer: VisionAnalyzer | None = None,
    ) -> None:
        self._frame_source = frame_source
        self._detector = detector
        self._vision_analyzer = vision_analyzer

    def execute(self, request: FirstToolReportRequest) -> FirstToolReportResult:
        self._validate(request)
        if request.send_frame_to_openai and self._vision_analyzer is None:
            raise ValueError("A análise GPT-4o foi solicitada, mas o analisador não está configurado.")

        streaks: dict[int, tuple[int, int, float, object, ToolDetection]] = {}
        first_frame: object | None = None
        first_index: int | None = None
        first_timestamp: float | None = None
        confirmation_frame_index: int | None = None
        confirmed: tuple[ConfirmedDetection, ...] = ()

        for frame_index, fps, frame in self._frame_source.frames(
            request.video_path, request.start_seconds, request.end_seconds
        ):
            by_class: dict[int, ToolDetection] = {}
            for detection in self._detector.detect(frame, request.confidence, request.device):
                existing = by_class.get(detection.class_id)
                if existing is None or detection.confidence > existing.confidence:
                    by_class[detection.class_id] = detection

            next_streaks: dict[int, tuple[int, int, float, object, ToolDetection]] = {}
            for class_id in by_class:
                previous = streaks.get(class_id)
                if previous is None:
                    next_streaks[class_id] = (1, frame_index, fps, frame.copy() if hasattr(frame, "copy") else frame, by_class[class_id])
                else:
                    count, initial_index, initial_fps, initial_frame, initial_detection = previous
                    next_streaks[class_id] = (count + 1, initial_index, initial_fps, initial_frame, initial_detection)
            streaks = next_streaks

            qualified = tuple(
                ConfirmedDetection(streaks[class_id][4], streaks[class_id][0])
                for class_id, detection in sorted(by_class.items())
                if streaks[class_id][0] >= request.consecutive_frames
            )
            if qualified:
                earliest_class = min(qualified, key=lambda item: streaks[item.detection.class_id][1]).detection.class_id
                _, first_index, first_fps, first_frame, _ = streaks[earliest_class]
                first_timestamp = first_index / first_fps
                confirmation_frame_index = frame_index
                confirmed = qualified
                break

        if first_frame is None or first_index is None or first_timestamp is None or confirmation_frame_index is None:
            raise RuntimeError("Nenhuma ferramenta foi confirmada no trecho informado.")

        output_dir = request.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{request.video_path.stem}-first-tool-frame-{first_index:06d}"
        frame_path = output_dir / f"{stem}.jpg"
        json_path = output_dir / f"{stem}.json"
        markdown_path = output_dir / f"{stem}.md"
        if any(path.exists() for path in (frame_path, json_path, markdown_path)):
            raise FileExistsError(f"Já existem artefatos desta detecção em {output_dir}; escolha outra pasta.")

        vision_description = None
        if request.send_frame_to_openai:
            assert self._vision_analyzer is not None
            vision_description = self._vision_analyzer.describe(
                first_frame, confirmed, request.openai_model
            )

        try:
            import cv2
        except ImportError as error:
            raise RuntimeError("OpenCV é necessário para salvar o frame selecionado.") from error
        if not cv2.imwrite(str(frame_path), first_frame):
            raise RuntimeError(f"Não foi possível salvar o frame selecionado: {frame_path}")

        payload = {
            "video": str(request.video_path),
            "frame": first_index,
            "timestamp_seconds": round(first_timestamp, 6),
            "confirmation_frame": confirmation_frame_index,
            "confirmation_timestamp_seconds": round(confirmation_frame_index / fps, 6),
            "analysis_interval_seconds": {
                "start": request.start_seconds,
                "end": request.end_seconds,
            },
            "detector": {
                "weights": str(request.weights_path),
                "confidence_threshold": request.confidence,
                "confirmation_consecutive_frames": request.consecutive_frames,
                "device": request.device,
            },
            "detections": [
                {
                    "class_id": item.detection.class_id,
                    "class_name": item.detection.class_name,
                    "confidence": round(item.detection.confidence, 6),
                    "box_xyxy": [round(value, 2) for value in item.detection.box_xyxy],
                    "consecutive_frames": item.consecutive_frames,
                    "source": "YOLO prediction; not independently verified",
                }
                for item in confirmed
            ],
            "vision_analysis": {
                "provider": "OpenAI" if vision_description is not None else None,
                "model": request.openai_model if vision_description is not None else None,
                "frame_sent_externally": vision_description is not None,
                "description": vision_description,
            },
            "limitations": (
                "Relatório técnico experimental para revisão humana; não constitui "
                "confirmação da detecção, diagnóstico ou orientação clínica."
            ),
        }
        try:
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            markdown_path.write_text(self._markdown(payload), encoding="utf-8")
        except Exception:
            frame_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            markdown_path.unlink(missing_ok=True)
            raise
        return FirstToolReportResult(
            frame_path=frame_path,
            json_path=json_path,
            markdown_path=markdown_path,
            frame_index=first_index,
            timestamp_seconds=first_timestamp,
            detections=confirmed,
            vision_description=vision_description,
            confirmation_frame_index=confirmation_frame_index,
        )

    @staticmethod
    def _validate(request: FirstToolReportRequest) -> None:
        if not request.video_path.is_file():
            raise FileNotFoundError(f"Vídeo não encontrado: {request.video_path}")
        if not request.weights_path.is_file():
            raise FileNotFoundError(f"Pesos do modelo não encontrados: {request.weights_path}")
        if request.start_seconds < 0:
            raise ValueError("O início do trecho não pode ser negativo.")
        if request.end_seconds is not None and request.end_seconds <= request.start_seconds:
            raise ValueError("O fim do trecho deve ser maior que o início.")
        if not 0 < request.confidence <= 1:
            raise ValueError("A confiança deve estar no intervalo (0, 1].")
        if request.consecutive_frames < 1:
            raise ValueError("A confirmação precisa exigir pelo menos um frame consecutivo.")
        if not request.openai_model.strip():
            raise ValueError("O nome do modelo OpenAI não pode ser vazio.")

    @staticmethod
    def _markdown(payload: dict[str, object]) -> str:
        detections = payload["detections"]
        assert isinstance(detections, list)
        lines = [
            "# Relatório técnico de primeira detecção",
            "",
            "> Resultado experimental para revisão humana; não é confirmação independente, diagnóstico ou orientação clínica.",
            "",
            f"- Vídeo: `{payload['video']}`",
            f"- Frame: {payload['frame']}",
            f"- Timestamp: {payload['timestamp_seconds']:.3f} s",
            f"- Confirmação da sequência: frame {payload['confirmation_frame']} ",
            "",
            "## Previsões do detector YOLO",
            "",
            "As classes abaixo são previsões do detector, não verificadas independentemente.",
            "",
        ]
        for detection in detections:
            lines.append(
                f"- **{detection['class_name']}** — confiança {detection['confidence']:.3f}; "
                f"caixa {detection['box_xyxy']}; confirmação em "
                f"{detection['consecutive_frames']} frames consecutivos."
            )
        vision = payload["vision_analysis"]
        assert isinstance(vision, dict)
        if vision["description"] is not None:
            lines.extend(("", "## Descrição visual gerada por GPT-4o", "", str(vision["description"])))
            lines.extend(("", "A descrição é gerada por IA e não valida a classe prevista pelo YOLO."))
        else:
            lines.extend(("", "## Análise visual", "", "Não solicitada; nenhum frame foi enviado à OpenAI."))
        lines.extend(("", "## Frame selecionado", "", f"`{Path(str(payload['video'])).stem}-first-tool-frame-{payload['frame']:06d}.jpg`", ""))
        return "\n".join(lines)
