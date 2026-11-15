from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from therapy_audio.models import (
    SegmentSentiment,
    TherapyAudioRequest,
    TherapyAudioResult,
    TranscriptSegment,
)


class AudioExtractor(Protocol):
    def extract(
        self,
        video_path: Path,
        output_path: Path,
        duration_seconds: int | None = None,
        start_seconds: int = 0,
    ) -> Path: ...


class SpeechTranscriber(Protocol):
    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]: ...


class SentimentAnalyzer(Protocol):
    def analyze(self, text: str) -> tuple[str, dict[str, float]]: ...


@dataclass(frozen=True)
class ProcessedTherapyVideo:
    audio_path: Path
    transcript_path: Path
    transcript: str
    segment_sentiments: list[SegmentSentiment]


class ProcessTherapyVideo:
    def __init__(
        self,
        audio_extractor: AudioExtractor,
        transcriber: SpeechTranscriber,
        sentiment_analyzer: SentimentAnalyzer,
    ) -> None:
        self._audio_extractor = audio_extractor
        self._transcriber = transcriber
        self._sentiment_analyzer = sentiment_analyzer

    def execute(self, request: TherapyAudioRequest) -> TherapyAudioResult:
        video_path = request.video_path.expanduser().resolve()
        output_dir = request.output_dir.expanduser().resolve()
        if not video_path.is_file():
            raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")
        if video_path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
            raise ValueError("Formato de vídeo não suportado. Use MP4, MOV, MKV, AVI ou WebM.")
        if request.test_duration_seconds is not None and request.test_duration_seconds <= 0:
            raise ValueError("A duração do teste deve ser um número de segundos maior que zero.")
        if request.start_seconds < 0:
            raise ValueError("O início do período não pode ser negativo.")

        output_dir.mkdir(parents=True, exist_ok=True)
        sequence = 1
        while True:
            output_stem = f"{video_path.stem}-{sequence:03d}"
            audio_path = output_dir / f"{output_stem}.wav"
            transcript_path = output_dir / f"{output_stem}-transcricao.txt"
            chunks_dir = output_dir / f"{output_stem}-chunks"
            if not audio_path.exists() and not transcript_path.exists() and not chunks_dir.exists():
                break
            sequence += 1

        produced_transcript = False
        try:
            produced_audio = self._audio_extractor.extract(
                video_path,
                audio_path,
                request.test_duration_seconds,
                request.start_seconds,
            )
            transcript_segments = self._transcriber.transcribe(produced_audio)
            transcript_segments = [segment for segment in transcript_segments if segment.text.strip()]
            if not transcript_segments:
                raise RuntimeError("O serviço de transcrição não retornou texto.")
            transcript = "\n".join(
                f"[{segment.start_seconds:.2f}s–{segment.end_seconds:.2f}s] {segment.text.strip()}"
                for segment in transcript_segments
            )
            transcript_path.write_text(transcript + "\n", encoding="utf-8")
            produced_transcript = True
            segment_sentiments: list[SegmentSentiment] = []
            for segment in transcript_segments:
                sentiment, scores = self._sentiment_analyzer.analyze(segment.text)
                segment_sentiments.append(
                    SegmentSentiment(segment, sentiment, scores)
                )
        except Exception:
            if produced_transcript:
                transcript_path.unlink(missing_ok=True)
            raise

        return TherapyAudioResult(
            audio_path=audio_path,
            transcript_path=transcript_path,
            transcript=transcript,
            segment_sentiments=segment_sentiments,
            aws_region=request.aws_region,
        )
