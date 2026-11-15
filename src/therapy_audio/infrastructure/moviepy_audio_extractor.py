from pathlib import Path


class MoviePyAudioExtractor:
    def extract(
        self,
        video_path: Path,
        output_path: Path,
        duration_seconds: int | None = None,
        start_seconds: int = 0,
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
            if start_seconds >= clip.duration:
                raise ValueError(
                    f"O início do período ({start_seconds}s) está fora da duração do vídeo "
                    f"({clip.duration:.1f}s)."
                )
            if duration_seconds is not None:
                end_seconds = start_seconds + duration_seconds
                if end_seconds > clip.duration:
                    raise ValueError(
                        f"O período termina em {end_seconds}s, além da duração do vídeo "
                        f"({clip.duration:.1f}s)."
                    )
                audio = audio.subclipped(start_seconds, end_seconds)
            elif start_seconds:
                audio = audio.subclipped(start_seconds, clip.duration)
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
