import argparse
from pathlib import Path
import sys

from video_review.application.track_video import TrackVideo
from video_review.infrastructure.opencv_video_tracker import OpenCvVideoTracker
from video_review.models import TrackingRequest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO = PROJECT_ROOT / "resources/cholec80/videos/video01.mp4"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seleciona uma caixa manualmente, rastreia com OpenCV e salva o resultado."
    )
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO, help="Vídeo de entrada")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "resources/cholec80/tracking/video01-tracked.mp4",
        help="Vídeo anotado de saída (padrão: primeiro vídeo do Cholec80)",
    )
    parser.add_argument("--tracker", choices=("CSRT", "KCF"), default="CSRT")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    video_path = args.video.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    use_case = TrackVideo(OpenCvVideoTracker())
    request = TrackingRequest(video_path, output_path, args.tracker)

    try:
        result = use_case.execute(request)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print(f"Frames processados: {result.frames_processed}")
    print(f"Falhas de rastreamento: {result.tracking_failures}")
    print(f"Vídeo anotado: {result.output_path}")
    print(f"Coordenadas por frame: {result.annotations_path}")
    if result.stopped_by_user:
        print("Processamento interrompido pelo usuário; saídas parciais foram salvas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
