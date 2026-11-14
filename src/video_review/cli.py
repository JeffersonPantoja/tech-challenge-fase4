import argparse
from pathlib import Path
import sys

from video_review.application.dataset import prepare_yolo_dataset, validate_tracking_data
from video_review.application.predict_video import PredictVideo, PredictionRequest
from video_review.application.train_detector import TrainDetector, TrainingRequest
from video_review.application.track_video import TOOL_CLASSES, TrackVideo
from video_review.infrastructure.opencv_video_tracker import OpenCvVideoTracker
from video_review.infrastructure.ultralytics_trainer import UltralyticsTrainer
from video_review.infrastructure.ultralytics_video_predictor import UltralyticsVideoPredictor
from video_review.models import TrackingRequest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO = PROJECT_ROOT / "resources/cholec80/videos/video01.mp4"
DEFAULT_TRACKING_ROOT = PROJECT_ROOT / "resources/cholec80/tracking"
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "resources/datasets/cholec80-yolo"


def _add_track_parser(subparsers) -> None:
    parser = subparsers.add_parser("track", help="Rastrear uma ferramenta e gerar imagens/labels")
    parser.add_argument("-v", "--video", type=Path, default=DEFAULT_VIDEO, help="Caminho do vídeo de entrada")
    parser.add_argument("--tool", choices=TOOL_CLASSES, required=True, help="Classe da ferramenta rastreada")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_TRACKING_ROOT, help="Pasta raiz dos rastreamentos")
    parser.add_argument("--tracker", choices=("CSRT", "KCF"), default="CSRT")
    parser.set_defaults(handler=_track)


def _add_data_parser(subparsers) -> None:
    parser = subparsers.add_parser("data", help="Validar e preparar os rastreamentos para YOLO")
    commands = parser.add_subparsers(dest="data_command", required=True)

    validate = commands.add_parser("validate", help="Validar imagens e labels dos rastreamentos")
    validate.add_argument("--tracking-root", type=Path, default=DEFAULT_TRACKING_ROOT)
    validate.set_defaults(handler=_validate_data)

    prepare = commands.add_parser("prepare", help="Recriar o dataset YOLO, dividido por blocos temporais")
    prepare.add_argument("--tracking-root", type=Path, default=DEFAULT_TRACKING_ROOT)
    prepare.add_argument("--output", type=Path, default=DEFAULT_DATASET_ROOT)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--block-seconds", type=float, default=30.0, help="Duração dos blocos contínuos")
    prepare.add_argument("--gap-seconds", type=float, default=2.0, help="Lacuna total entre partições temporais diferentes")
    prepare.add_argument("--fps", type=float, default=25.0, help="FPS do vídeo de origem para converter frames em tempo")
    prepare.set_defaults(handler=_prepare_data)


def _add_detector_parser(subparsers) -> None:
    parser = subparsers.add_parser("detector", help="Treinar e executar o detector YOLO")
    commands = parser.add_subparsers(dest="detector_command", required=True)

    train = commands.add_parser("train", help="Treinar YOLOv8 com o dataset preparado")
    train.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_ROOT / "data.yaml")
    train.add_argument("--model", default="yolov8n.pt", help="Checkpoint inicial ou caminho para pesos")
    train.add_argument("--epochs", type=int, default=50)
    train.add_argument("--imgsz", type=int, default=640)
    train.add_argument("--batch", type=int, default=2)
    train.add_argument("--device", default=None, help="Ex.: 0, cpu; padrão: seleção automática Ultralytics")
    train.add_argument("--project", type=Path, default=PROJECT_ROOT / "runs/detect")
    train.add_argument("--name", default="cholec80-yolov8n")
    train.set_defaults(handler=_train_detector)

    predict = commands.add_parser("predict", help="Executar o modelo em um vídeo cirúrgico")
    predict.add_argument("--video", type=Path, required=True)
    predict.add_argument("--weights", type=Path, required=True, help="Pesos .pt treinados")
    predict.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "resources/results")
    predict.add_argument("--conf", type=float, default=0.25, help="Confiança mínima entre 0 e 1")
    predict.add_argument("--device", default=None, help="Ex.: 0, cpu; padrão: seleção automática Ultralytics")
    predict.set_defaults(handler=_predict_video)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rastreamento, preparação de dataset, treinamento e inferência YOLOv8."
    )
    commands = parser.add_subparsers(dest="command")
    _add_track_parser(commands)
    _add_data_parser(commands)
    _add_detector_parser(commands)
    return parser


def _path(path: Path) -> Path:
    return path.expanduser().resolve()


def _print_summary(summary) -> None:
    print(f"Imagens únicas: {summary.image_count}")
    print(f"Vídeos de origem: {summary.video_count}")
    print(f"Rastreamentos vazios ignorados: {summary.empty_runs}")
    if summary.excluded_frames:
        print(f"Frames removidos nas lacunas temporais: {summary.excluded_frames}")
    print("Caixas por classe:")
    for name, count in summary.class_counts.items():
        print(f"  {name}: {count}")


def _track(args) -> int:
    request = TrackingRequest(_path(args.video), _path(args.output_root), args.tool, args.tracker)
    result = TrackVideo(OpenCvVideoTracker()).execute(request)
    print(f"Frames processados: {result.frames_processed}")
    print(f"Falhas de rastreamento: {result.tracking_failures}")
    print(f"Ferramenta: {result.tool_class}; sequência: {result.sequence_number:03d}")
    print(f"Imagens e labels YOLO: {result.output_path}")
    if result.stopped_by_user:
        print("Processamento interrompido pelo usuário; saídas parciais foram salvas.")
    return 0


def _validate_data(args) -> int:
    summary = validate_tracking_data(_path(args.tracking_root))
    print("Rastreamentos válidos.")
    _print_summary(summary)
    return 0


def _prepare_data(args) -> int:
    summary = prepare_yolo_dataset(
        _path(args.tracking_root),
        _path(args.output),
        seed=args.seed,
        block_seconds=args.block_seconds,
        gap_seconds=args.gap_seconds,
        fps=args.fps,
    )
    print(f"Dataset YOLO recriado em: {_path(args.output)}")
    print(f"Configuração: {_path(args.output) / 'data.yaml'}")
    print(f"Manifesto das partições: {_path(args.output) / 'split_manifest.json'}")
    _print_summary(summary)
    return 0


def _train_detector(args) -> int:
    request = TrainingRequest(
        dataset_yaml=_path(args.dataset),
        model=args.model,
        epochs=args.epochs,
        image_size=args.imgsz,
        batch_size=args.batch,
        device=args.device,
        project=_path(args.project),
        name=args.name,
    )
    best_weights = TrainDetector(UltralyticsTrainer()).execute(request)
    print(f"Melhores pesos: {best_weights}")
    return 0


def _predict_video(args) -> int:
    request = PredictionRequest(
        video_path=_path(args.video),
        weights_path=_path(args.weights),
        output_dir=_path(args.output_dir),
        confidence=args.conf,
        device=args.device,
    )
    result = PredictVideo(UltralyticsVideoPredictor()).execute(request)
    print(f"Frames processados: {result.frames_processed}")
    print(f"Detecções: {result.detection_count}")
    print(f"Vídeo anotado: {result.output_video}")
    print(f"Detecções por frame: {result.detections_csv}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    commands = {"track", "data", "detector"}
    # Mantém compatibilidade com a CLI antiga: opções sem subcomando significam track.
    if args_list and args_list[0] not in commands and args_list[0] not in {"-h", "--help"}:
        args_list.insert(0, "track")
    args = build_parser().parse_args(args_list)
    if not hasattr(args, "handler"):
        build_parser().print_help()
        return 0
    try:
        return args.handler(args)
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
