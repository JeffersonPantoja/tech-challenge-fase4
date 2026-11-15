from pathlib import Path
import logging

from therapy_audio.models import TranscriptSegment


logger = logging.getLogger(__name__)


class GoogleSpeechTranscriber:
    def __init__(
        self,
        language: str = "pt-BR",
        max_chunk_seconds: int = 45,
        silence_threshold_dbfs: float = -35.0,
        min_silence_ms: int = 350,
        silence_padding_ms: int = 120,
    ) -> None:
        if max_chunk_seconds < 5:
            raise ValueError("A duração máxima por trecho deve ser de pelo menos 5 segundos.")
        self._language = language
        self._max_chunk_ms = max_chunk_seconds * 1000
        self._silence_threshold_dbfs = silence_threshold_dbfs
        self._min_silence_ms = min_silence_ms
        self._silence_padding_ms = silence_padding_ms

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        try:
            import speech_recognition as sr
            from pydub import AudioSegment, silence
        except ImportError as error:
            raise RuntimeError(
                "SpeechRecognition/pydub não estão instalados. Instale as dependências com: "
                ".venv/bin/pip install -r requirements.txt"
            ) from error

        recognizer = sr.Recognizer()
        chunks_dir = audio_path.parent / f"{audio_path.stem}-chunks"
        chunks_dir_created = False
        try:
            sound = AudioSegment.from_file(audio_path).set_channels(1).set_frame_rate(16000)
            if len(sound) == 0:
                raise RuntimeError(f"O arquivo de áudio está vazio: {audio_path}")

            chunks_dir.mkdir(parents=True, exist_ok=False)
            chunks_dir_created = True
            chunks = self._split_at_silence(sound, silence)
            logger.info(
                "Áudio de %.1fs dividido em %d trechos de até %.1fs usando pausas "
                "(limiar %.1f dBFS, silêncio mínimo %dms).",
                len(sound) / 1000,
                len(chunks),
                self._max_chunk_ms / 1000,
                self._silence_threshold_dbfs,
                self._min_silence_ms,
            )

            transcripts: list[TranscriptSegment] = []
            for index, (start_ms, end_ms) in enumerate(chunks, start=1):
                chunk_path = chunks_dir / f"chunk-{index:04d}.wav"
                sound[start_ms:end_ms].export(chunk_path, format="wav")
                with sr.AudioFile(str(chunk_path)) as source:
                    audio = recognizer.record(source)
                logger.info(
                    "Transcrevendo trecho %d/%d: %.2fs–%.2fs (%.2fs), idioma=%s",
                    index,
                    len(chunks),
                    start_ms / 1000,
                    end_ms / 1000,
                    (end_ms - start_ms) / 1000,
                    self._language,
                )
                try:
                    text = recognizer.recognize_google(audio, language=self._language)
                except sr.UnknownValueError:
                    logger.warning("Fala não reconhecida no trecho %d; continuando.", index)
                    continue
                text = text.strip()
                if text:
                    transcripts.append(
                        TranscriptSegment(
                            index=index,
                            start_seconds=start_ms / 1000,
                            end_seconds=end_ms / 1000,
                            text=text,
                        )
                    )
            if not transcripts:
                raise RuntimeError("O serviço não reconheceu fala em nenhum trecho do áudio.")
            return transcripts
        except sr.UnknownValueError as error:
            logger.exception("Google Speech Recognition recebeu áudio, mas não o compreendeu.")
            raise RuntimeError("O serviço de reconhecimento não conseguiu entender o áudio.") from error
        except sr.RequestError as error:
            logger.exception("Falha de comunicação com Google Speech Recognition: %s", error)
            raise RuntimeError(f"Falha ao solicitar transcrição ao serviço Google: {error}") from error
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError(f"Falha ao preparar ou segmentar o áudio: {error}") from error
        finally:
            if chunks_dir_created and chunks_dir.exists():
                for chunk_path in chunks_dir.glob("chunk-*.wav"):
                    chunk_path.unlink(missing_ok=True)
                chunks_dir.rmdir()

    def _split_at_silence(self, sound, silence_module) -> list[tuple[int, int]]:
        duration_ms = len(sound)
        boundaries = silence_module.detect_silence(
            sound,
            min_silence_len=self._min_silence_ms,
            silence_thresh=self._silence_threshold_dbfs,
            seek_step=10,
        )
        # Corta no meio das pausas detectadas e remove apenas uma pequena borda
        # silenciosa de cada lado, mantendo as palavras fora da região de silêncio.
        silent_centers = [
            (start + end) // 2
            for start, end in boundaries
            if end - start >= self._min_silence_ms
        ]

        chunks: list[tuple[int, int]] = []
        start_ms = 0
        while duration_ms - start_ms > self._max_chunk_ms:
            target = start_ms + self._max_chunk_ms
            candidates = [
                point
                for point in silent_centers
                if start_ms + 1000 <= point <= target
            ]
            if candidates:
                boundary = min(candidates, key=lambda point: abs(point - target))
            else:
                # Não existe pausa segura dentro do limite; avançar até a próxima pausa
                # em vez de cortar a fala. O segmento poderá exceder o limite configurado.
                future = [point for point in silent_centers if point > target]
                if not future:
                    raise RuntimeError(
                        "Não foi encontrada pausa para segmentar o áudio perto do limite. "
                        "Aumente --max-chunk-seconds ou revise o nível de silêncio."
                    )
                boundary = future[0]
            cut = max(start_ms + 1, boundary - self._silence_padding_ms)
            chunks.append((start_ms, cut))
            start_ms = min(duration_ms, boundary + self._silence_padding_ms)

        if start_ms < duration_ms:
            chunks.append((start_ms, duration_ms))
        if not chunks:
            chunks.append((0, duration_ms))
        if any(end <= start for start, end in chunks):
            raise RuntimeError("A detecção de silêncio gerou trechos inválidos.")
        return chunks
