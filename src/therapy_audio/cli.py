import argparse
import logging
from pathlib import Path
import sys

from therapy_audio.application.process_video import ProcessTherapyVideo
from therapy_audio.infrastructure.aws_comprehend_sentiment import AwsComprehendSentimentAnalyzer
from therapy_audio.infrastructure.google_speech_transcriber import GoogleSpeechTranscriber
from therapy_audio.infrastructure.moviepy_audio_extractor import MoviePyAudioExtractor
from therapy_audio.models import TherapyAudioRequest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "resources/therapy-audio"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extrai áudio, transcreve em pt-BR e analisa sentimento com AWS Comprehend."
    )
    parser.add_argument("video", type=Path, help="Caminho local do vídeo de entrada")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Pasta de saída (padrão: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--aws-region",
        default="us-east-1",
        help="Região AWS do Comprehend (padrão: us-east-1)",
    )
    parser.add_argument(
        "--max-chunk-seconds",
        type=int,
        default=45,
        help="Duração alvo máxima dos trechos de transcrição (padrão: 45s)",
    )
    parser.add_argument(
        "--test-seconds",
        type=int,
        metavar="SEGUNDOS",
        help="Atalho: processar os primeiros N segundos (equivale a --start-seconds 0 --duration-seconds N)",
    )
    parser.add_argument(
        "--start-seconds",
        type=int,
        default=0,
        metavar="SEGUNDOS",
        help="Início do período do vídeo em segundos (padrão: 0)",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        metavar="SEGUNDOS",
        help="Duração do período a processar; omitindo, vai do início até o fim do vídeo",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Exibir logs técnicos detalhados (não inclui o conteúdo do áudio nem credenciais)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.test_seconds is not None and args.duration_seconds is not None:
        build_parser().error("--test-seconds não pode ser usado junto com --duration-seconds")
    if args.test_seconds is not None and args.start_seconds != 0:
        build_parser().error("--test-seconds processa desde o início; não use com --start-seconds")
    duration_seconds = args.duration_seconds if args.test_seconds is None else args.test_seconds
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    video_path = args.video.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    try:
        print("Aviso: o áudio será enviado ao reconhecimento de fala Google e o texto à AWS Comprehend.")
        use_case = ProcessTherapyVideo(
            MoviePyAudioExtractor(),
            GoogleSpeechTranscriber(max_chunk_seconds=args.max_chunk_seconds),
            AwsComprehendSentimentAnalyzer(args.aws_region),
        )
        result = use_case.execute(
            TherapyAudioRequest(
                video_path,
                output_dir,
                args.aws_region,
                test_duration_seconds=duration_seconds,
                start_seconds=args.start_seconds,
            )
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        if args.verbose:
            logger = logging.getLogger(__name__)
            logger.exception("Pipeline encerrado com erro")
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print("\n=== Resultado da análise de sentimento ===")
    print(f"Sentimento: {result.sentiment}")
    print("Pontuações:")
    for label, score in result.sentiment_scores.items():
        print(f"  {label}: {score:.4f}")
    print(f"Transcrição: {result.transcript}")
    print(f"Áudio extraído: {result.audio_path}")
    print(f"Transcrição salva em: {result.transcript_path}")
    print("Interprete a classificação como polaridade textual, não como avaliação clínica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
