from pathlib import Path

from video_review.application.track_video import TOOL_CLASSES
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

        output_directory = request.output_root.expanduser().resolve() / request.tool_class
        output_directory.mkdir(parents=True, exist_ok=True)
        sequence_numbers = [
            int(path.name.split("_", 1)[0])
            for path in output_directory.glob("[0-9][0-9][0-9]_*")
            if path.name.split("_", 1)[0].isdigit()
        ]
        sequence_number = max(sequence_numbers, default=0) + 1
        stem = f"{sequence_number:03d}_{request.video_path.stem}"
        sequence_directory = output_directory / stem
        images_directory = sequence_directory / "images"
        labels_directory = sequence_directory / "labels"
        images_directory.mkdir(parents=True)
        labels_directory.mkdir()
        output_path = sequence_directory

        capture = cv2.VideoCapture(str(request.video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Não foi possível abrir o vídeo: {request.video_path}")

        frames_processed = 0
        failures = 0
        stopped_by_user = False
        window_name = "Frame inicial: A/D = 15 frames | J/L = 100 frames | ENTER seleciona | ESC cancela"

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
                        f"Frame {frame_index} / {max(total_frames - 1, 0)} | A: -15, D: +15 | J: -100, L: +100 | ENTER: escolher | ESC: cancelar",
                        (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2,
                    )
                    cv2.imshow(window_name, preview)
                    key = cv2.waitKey(0) & 0xFF
                    if key in (13, 10):
                        break
                    if key == 27:
                        raise RuntimeError("Seleção do frame inicial cancelada.")
                    if key == ord("a"):
                        frame_index = max(0, frame_index - 15)
                    elif key == ord("d"):
                        frame_index = min(max(total_frames - 1, 0), frame_index + 15)
                    elif key == ord("j"):
                        frame_index = max(0, frame_index - 100)
                    elif key == ord("l"):
                        frame_index = min(max(total_frames - 1, 0), frame_index + 100)
                    else:
                        continue
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ok, preview_frame = capture.read()
                    if not ok:
                        raise RuntimeError(f"Não foi possível ler o frame {frame_index}.")

                initial_frame = preview_frame
                initial_frame_index = frame_index
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
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index + 1)
            current_frame = initial_frame
            current_box = (x, y, box_width, box_height)
            tracking_ok = True

            while True:
                image_name = f"frame_{frame_index:06d}.jpg"
                label_path = labels_directory / f"frame_{frame_index:06d}.txt"
                training_frame = current_frame.copy()
                if tracking_ok:
                    x, y, box_width, box_height = current_box
                    # Recorta a caixa na borda do frame, mantendo a porção visível no rótulo YOLO.
                    x1, y1 = max(0, x), max(0, y)
                    x2, y2 = min(width, x + box_width), min(height, y + box_height)
                    if x1 < x2 and y1 < y2:
                        clipped_x = x1
                        clipped_y = y1
                        clipped_width = x2 - x1
                        clipped_height = y2 - y1
                        center_x = ((x1 + x2) / 2) / width
                        center_y = ((y1 + y2) / 2) / height
                        normalized_width = (x2 - x1) / width
                        normalized_height = (y2 - y1) / height
                        label_path.write_text(
                            f"{TOOL_CLASSES.index(request.tool_class)} "
                            f"{center_x:.6f} {center_y:.6f} "
                            f"{normalized_width:.6f} {normalized_height:.6f}\n",
                            encoding="utf-8",
                        )
                        x, y, box_width, box_height = clipped_x, clipped_y, clipped_width, clipped_height
                    else:
                        failures += 1
                        tracking_ok = False
                if not tracking_ok:
                    label_path.write_text("", encoding="utf-8")
                    cv2.putText(current_frame, "Rastreamento perdido/caixa fora do frame", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                if not cv2.imwrite(str(images_directory / image_name), training_frame):
                    raise RuntimeError(f"Não foi possível salvar o frame {frame_index}.")
                if tracking_ok:
                    cv2.rectangle(current_frame, (x, y), (x + box_width, y + box_height), (0, 255, 0), 2)
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
            cv2.destroyAllWindows()

        return TrackingResult(
            video_path=request.video_path,
            tool_class=request.tool_class,
            sequence_number=sequence_number,
            output_path=output_path,
            tracker_name=request.tracker_name.upper(),
            frames_processed=frames_processed,
            tracking_failures=failures,
            stopped_by_user=stopped_by_user,
        )
