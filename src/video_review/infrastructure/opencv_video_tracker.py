import csv
from pathlib import Path

from video_review.models import TrackingRequest, TrackingResult


class OpenCvVideoTracker:
    """Implementa a seleção manual de ROI e o rastreamento KCF/CSRT com OpenCV."""

    @staticmethod
    def _create_tracker(cv2, tracker_name: str):
        name = tracker_name.upper()
        factory_names = (f"Tracker{name}_create",)
        for namespace in (cv2, getattr(cv2, "legacy", None)):
            if namespace is None:
                continue
            for factory_name in factory_names:
                factory = getattr(namespace, factory_name, None)
                if factory is not None:
                    return factory()
        raise RuntimeError(
            f"O rastreador {name} não está disponível nesta instalação do OpenCV. "
            "Instale as dependências com: .venv/bin/pip install -r requirements.txt"
        )

    def track(self, request: TrackingRequest) -> TrackingResult:
        try:
            import cv2
        except ImportError as error:
            raise RuntimeError(
                "OpenCV não está instalado. Execute: "
                ".venv/bin/pip install -r requirements.txt"
            ) from error

        output_path = request.output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotations_path = output_path.with_suffix(".csv")

        capture = cv2.VideoCapture(str(request.video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Não foi possível abrir o vídeo: {request.video_path}")

        writer = None
        frames_processed = 0
        failures = 0
        stopped_by_user = False
        window_name = "Selecione frame inicial: A/D ou setas; ENTER seleciona; ESC cancela"

        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                raise RuntimeError("Não foi possível obter o FPS do vídeo.")

            ok, preview_frame = capture.read()
            if not ok:
                raise RuntimeError("Não foi possível ler o primeiro frame do vídeo.")

            if request.display:
                frame_index = 0
                total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                while True:
                    preview = preview_frame.copy()
                    cv2.putText(
                        preview,
                        f"Frame {frame_index} / {max(total_frames - 1, 0)} | A/D ou setas: navegar | ENTER: escolher | ESC: cancelar",
                        (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2,
                    )
                    cv2.imshow(window_name, preview)
                    key = cv2.waitKey(0) & 0xFF
                    if key in (13, 10):
                        break
                    if key == 27:
                        raise RuntimeError("Seleção do frame inicial cancelada.")
                    if key in (ord("a"), 81):
                        frame_index = max(0, frame_index - 1)
                    elif key in (ord("d"), 83):
                        frame_index = min(max(total_frames - 1, 0), frame_index + 1)
                    else:
                        continue
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ok, preview_frame = capture.read()
                    if not ok:
                        raise RuntimeError(f"Não foi possível ler o frame {frame_index}.")

                initial_frame = preview_frame
                height, width = initial_frame.shape[:2]
                initial_box = cv2.selectROI(
                    "Desenhe a caixa da ferramenta e pressione ENTER",
                    initial_frame,
                    False,
                    False,
                )
                cv2.destroyWindow(window_name)
            else:
                raise RuntimeError("A seleção da caixa inicial exige uma janela gráfica.")

            x, y, box_width, box_height = (int(value) for value in initial_box)
            if box_width <= 0 or box_height <= 0:
                raise RuntimeError("Nenhuma caixa foi selecionada; rastreamento cancelado.")

            tracker = self._create_tracker(cv2, request.tracker_name)
            tracker.init(initial_frame, (x, y, box_width, box_height))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            if not writer.isOpened():
                raise RuntimeError(f"Não foi possível criar o vídeo de saída: {output_path}")

            with annotations_path.open("w", newline="", encoding="utf-8") as csv_file:
                annotations = csv.writer(csv_file)
                annotations.writerow(
                    ["frame", "timestamp_seconds", "status", "x", "y", "width", "height"]
                )

                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index + 1)
                current_frame = initial_frame
                current_box = (x, y, box_width, box_height)
                tracking_ok = True

                while True:
                    timestamp = frame_index / fps
                    if tracking_ok:
                        x, y, box_width, box_height = current_box
                        cv2.rectangle(current_frame, (x, y), (x + box_width, y + box_height), (0, 255, 0), 2)
                        annotations.writerow(
                            [frame_index, f"{timestamp:.6f}", "initial" if frames_processed == 0 else "tracked", x, y, box_width, box_height]
                        )
                    writer.write(current_frame)
                    frames_processed += 1
                    if request.display:
                        cv2.imshow("Rastreamento — pressione ESC para encerrar", current_frame)
                        if cv2.waitKey(1) & 0xFF == 27:
                            stopped_by_user = True
                            break

                    ok, next_frame = capture.read()
                    if not ok:
                        break
                    frame_index += 1
                    current_frame = next_frame
                    tracking_ok, proposed_box = tracker.update(current_frame)
                    if tracking_ok:
                        current_box = tuple(int(value) for value in proposed_box)
                    else:
                        failures += 1

                    if not tracking_ok:
                        cv2.putText(current_frame, "Rastreamento perdido", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        finally:
            capture.release()
            if writer is not None:
                writer.release()
            cv2.destroyAllWindows()

        return TrackingResult(
            video_path=request.video_path,
            output_path=output_path,
            annotations_path=annotations_path,
            tracker_name=request.tracker_name.upper(),
            frames_processed=frames_processed,
            tracking_failures=failures,
            stopped_by_user=stopped_by_user,
        )
