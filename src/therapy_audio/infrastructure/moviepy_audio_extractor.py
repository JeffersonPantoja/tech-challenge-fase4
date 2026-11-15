from pathlib import Path


class MoviePyAudioExtractor:
    def extract(
        self, video_path: Path, output_path: Path, duration_seconds: int | None = None
    ) -> Path:
        try:
            from moviepy import VideoFileClip
        except ImportError:
            try:
                from moviepy.editor import VideoFileClip
            except ImportError as error:
                raise RuntimeError(
                    "MoviePy não está instalado. Instale as dependências com: "
                    ".venv/bin/pip install -r requirements.txt"
                ) from error

        clip = None
        try:
            clip = VideoFileClip(str(video_path))
            if clip.audio is None:
                raise RuntimeError(f"O vídeo não contém faixa de áudio: {video_path}")
            audio = clip.audio
            if duration_seconds is not None:
                if duration_seconds > clip.duration:
                    raise ValueError(
                        f"A duração do teste ({duration_seconds}s) excede a duração do vídeo "
                        f"({clip.duration:.1f}s)."
                    )
                audio = audio.subclipped(0, duration_seconds)
            audio.write_audiofile(
                str(output_path),
                fps=16000,
                nbytes=2,
                codec="pcm_s16le",
                logger=None,
            )
        except Exception as error:
            output_path.unlink(missing_ok=True)
            if isinstance(error, RuntimeError):
                raise
            raise RuntimeError(f"Falha ao extrair áudio do vídeo: {error}") from error
        finally:
            if clip is not None:
                clip.close()
        return output_path
