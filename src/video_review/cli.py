import argparse
from pathlib import Path
import sys

from video_review.application.track_video import TOOL_CLASSES, TrackVideo
from video_review.infrastructure.opencv_video_tracker import OpenCvVideoTracker
from video_review.models import TrackingRequest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO = PROJECT_ROOT / "resources/cholec80/videos/video01.mp4"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seleciona uma caixa manualmente, rastreia com OpenCV e salva imagens e rótulos YOLO.",
        epilog=(
            'Exemplo: python -m video_review.cli --video "resources/cholec80/videos/video02.mp4" '
            "--tool grasper"
        ),
    )
    parser.add_argument(
        "-v", "--video", type=Path, default=DEFAULT_VIDEO,
        help=f"Caminho do vídeo de entrada (padrão: {DEFAULT_VIDEO})",
    )
    parser.add_argument("--tool", choices=TOOL_CLASSES, required=True, help="Classe da ferramenta rastreada")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "resources/cholec80/tracking", help="Pasta raiz das saídas")
    parser.add_argument("--tracker", choices=("CSRT", "KCF"), default="CSRT")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    video_path = args.video.expanduser().resolve()
    use_case = TrackVideo(OpenCvVideoTracker())
    request = TrackingRequest(video_path, args.output_root.expanduser().resolve(), args.tool, args.tracker)

    try:
        result = use_case.execute(request)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print(f"Frames processados: {result.frames_processed}")
    print(f"Falhas de rastreamento: {result.tracking_failures}")
    print(f"Ferramenta: {result.tool_class}")
    print(f"Rastreamento: {result.sequence_number:03d}")
    print(f"Imagens e rótulos YOLO: {result.output_path}")
    if result.stopped_by_user:
        print("Processamento interrompido pelo usuário; saídas parciais foram salvas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
