from pathlib import Path
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from therapy_audio.application.process_video import ProcessTherapyVideo
from therapy_audio.infrastructure.google_speech_transcriber import GoogleSpeechTranscriber
from therapy_audio.infrastructure.openai_segment_analyzer import (
    ANALYSIS_SCHEMA,
    SYSTEM_PROMPT,
    OpenAISegmentAnalyzer,
)
from therapy_audio.models import TherapyAudioRequest, TranscriptSegment


class ProcessTherapyVideoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.video = self.root / "sessao.mp4"
        self.video.write_bytes(b"video input")
        self.output_dir = self.root / "out"
        self.extractor = Mock()
        self.transcriber = Mock()
        self.analyzer = Mock()
        self.use_case = ProcessTherapyVideo(self.extractor, self.transcriber, self.analyzer)
        self.request = TherapyAudioRequest(self.video, self.output_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_runs_all_steps_and_returns_artifacts(self) -> None:
        audio_path = self.output_dir / "sessao-001.wav"

        def extract(
            _video_path: Path, output_path: Path,
            _duration: int | None = None, _start: int = 0,
        ) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        self.extractor.extract.side_effect = extract
        self.transcriber.transcribe.return_value = [
            TranscriptSegment(1, 0.0, 10.0, "fala de teste")
        ]
        self.analyzer.analyze.return_value = ("NEUTRAL", {"Positive": 0.1, "Negative": 0.1, "Neutral": 0.8, "Mixed": 0.0})

        result = self.use_case.execute(self.request)

        self.assertEqual(result.audio_path, audio_path)
        self.assertEqual(result.transcript, "[0.00s–10.00s] fala de teste")
        self.assertEqual(result.segment_sentiments[0].sentiment, "NEUTRAL")
        self.assertEqual(
            result.transcript_path.read_text(encoding="utf-8"),
            "[0.00s–10.00s] fala de teste\n",
        )
        self.extractor.extract.assert_called_once_with(self.video.resolve(), audio_path, None, 0)
        self.transcriber.transcribe.assert_called_once_with(audio_path)
        self.analyzer.analyze.assert_called_once_with("fala de teste")

    def test_analyzes_sentiment_separately_for_each_transcribed_segment(self) -> None:
        def extract(
            _video_path: Path, output_path: Path,
            _duration: int | None = None, _start: int = 0,
        ) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        self.extractor.extract.side_effect = extract
        segments = [
            TranscriptSegment(1, 0, 12, "Estou bem."),
            TranscriptSegment(2, 12, 24, "Tenho sentido ansiedade."),
        ]
        self.transcriber.transcribe.return_value = segments
        self.analyzer.analyze.side_effect = [
            ("POSITIVE", {"Positive": 0.9}),
            ("NEGATIVE", {"Negative": 0.8}),
        ]

        result = self.use_case.execute(self.request)

        self.assertEqual([item.sentiment for item in result.segment_sentiments], ["POSITIVE", "NEGATIVE"])
        self.assertEqual(self.analyzer.analyze.call_args_list[0].args, ("Estou bem.",))
        self.assertEqual(self.analyzer.analyze.call_args_list[1].args, ("Tenho sentido ansiedade.",))

    def test_rejects_missing_video(self) -> None:
        request = TherapyAudioRequest(self.root / "missing.mp4", self.output_dir)
        with self.assertRaises(FileNotFoundError):
            self.use_case.execute(request)

    def test_does_not_overwrite_existing_artifacts(self) -> None:
        self.output_dir.mkdir()
        (self.output_dir / "sessao-001.wav").write_bytes(b"existing")
        (self.output_dir / "sessao-001-transcricao.txt").write_text("existing", encoding="utf-8")

        def extract(
            _video_path: Path, output_path: Path,
            _duration: int | None = None, _start: int = 0,
        ) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        self.extractor.extract.side_effect = extract
        self.transcriber.transcribe.return_value = [
            TranscriptSegment(1, 0, 10, "fala de teste")
        ]
        self.analyzer.analyze.return_value = ("NEUTRAL", {})
        result = self.use_case.execute(self.request)

        self.assertEqual(result.audio_path.name, "sessao-002.wav")
        self.assertEqual(result.transcript_path.name, "sessao-002-transcricao.txt")

    def test_preserves_audio_and_removes_partial_transcript_if_later_step_fails(self) -> None:
        def extract(
            _video_path: Path, output_path: Path,
            _duration: int | None = None, _start: int = 0,
        ) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        self.extractor.extract.side_effect = extract
        self.transcriber.transcribe.return_value = [
            TranscriptSegment(1, 0, 10, "fala de teste")
        ]
        self.analyzer.analyze.side_effect = RuntimeError("AWS indisponível")

        with self.assertRaisesRegex(RuntimeError, "AWS indisponível"):
            self.use_case.execute(self.request)
        self.assertTrue((self.output_dir / "sessao-001.wav").exists())
        self.assertFalse((self.output_dir / "sessao-001-transcricao.txt").exists())

    def test_rejects_non_positive_test_duration(self) -> None:
        request = TherapyAudioRequest(self.video, self.output_dir, test_duration_seconds=0)
        with self.assertRaisesRegex(ValueError, "maior que zero"):
            self.use_case.execute(request)
        self.extractor.extract.assert_not_called()


class SilenceSegmentationTests(unittest.TestCase):
    def test_splits_near_chunk_limit_at_detected_silence_centers(self) -> None:
        class FakeSilence:
            @staticmethod
            def detect_silence(*_args, **_kwargs):
                return [[40000, 41000], [85000, 86000]]

        class FakeSound:
            def __len__(self):
                return 100000

        transcriber = GoogleSpeechTranscriber(max_chunk_seconds=45, silence_padding_ms=100)
        chunks = transcriber._split_at_silence(FakeSound(), FakeSilence)

        self.assertEqual(chunks, [(0, 40400), (40600, 85400), (85600, 100000)])
        for previous, following in zip(chunks, chunks[1:]):
            self.assertLess(previous[1], following[0])

    def test_raises_if_no_silence_boundary_is_available(self) -> None:
        class FakeSilence:
            @staticmethod
            def detect_silence(*_args, **_kwargs):
                return []

        class FakeSound:
            def __len__(self):
                return 100000

        transcriber = GoogleSpeechTranscriber(max_chunk_seconds=45)
        with self.assertRaisesRegex(RuntimeError, "Não foi encontrada pausa"):
            transcriber._split_at_silence(FakeSound(), FakeSilence)


class OpenAISegmentAnalyzerTests(unittest.TestCase):
    def test_sends_segment_and_aws_results_with_structured_output(self) -> None:
        structured = {
            "aws_sentiment_interpretation": "NEGATIVE",
            "aws_scores_summary": "Negative dominante.",
            "critical_terms": [],
            "complementary_sentiment": "NEGATIVE",
            "sentiment_context": "Tom negativo no trecho.",
            "limitations": "Sem inferência clínica.",
        }
        response = Mock(output_text=json.dumps(structured))
        client = Mock()
        client.responses.create.return_value = response

        fake_openai = types.SimpleNamespace(OpenAI=Mock(return_value=client))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch.dict(
            sys.modules, {"openai": fake_openai}
        ):
            result = OpenAISegmentAnalyzer().analyze(
                "Estou muito triste.", "NEGATIVE", {"Negative": 0.98, "Positive": 0.01}
            )

        self.assertEqual(result, structured)
        fake_openai.OpenAI.assert_called_once_with()
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.4-mini")
        self.assertEqual(kwargs["input"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(kwargs["text"]["format"]["schema"], ANALYSIS_SCHEMA)
        self.assertIn("Estou muito triste.", kwargs["input"][1]["content"])
        self.assertIn('"sentiment": "NEGATIVE"', kwargs["input"][1]["content"])
        self.assertIn('"Negative": 0.98', kwargs["input"][1]["content"])

    def test_fails_without_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                OpenAISegmentAnalyzer().analyze("texto", "NEUTRAL", {})


class OptionalContextualAnalysisTests(ProcessTherapyVideoTests):
    def test_passes_each_segment_aws_result_to_contextual_analyzer(self) -> None:
        def extract(
            _video_path: Path, output_path: Path,
            _duration: int | None = None, _start: int = 0,
        ) -> Path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        self.extractor.extract.side_effect = extract
        segments = [TranscriptSegment(1, 0, 10, "Estou triste.")]
        self.transcriber.transcribe.return_value = segments
        self.analyzer.analyze.return_value = ("NEGATIVE", {"Negative": 0.9})
        contextual = Mock()
        contextual.analyze.return_value = {"critical_terms": []}
        use_case = ProcessTherapyVideo(
            self.extractor, self.transcriber, self.analyzer, contextual
        )
        request = TherapyAudioRequest(
            self.video, self.output_dir, openai_analysis=True
        )

        result = use_case.execute(request)

        contextual.analyze.assert_called_once_with(
            "Estou triste.", "NEGATIVE", {"Negative": 0.9}
        )
        self.assertEqual(result.segment_sentiments[0].gpt_analysis, {"critical_terms": []})


if __name__ == "__main__":
    unittest.main()
