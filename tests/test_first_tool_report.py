import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from video_review.application.first_tool_report import (
    FirstToolReport,
    FirstToolReportRequest,
    ToolDetection,
)


class FakeFrame:
    shape = (80, 120, 3)

    def __init__(self, index):
        self.index = index

    def copy(self):
        return FakeFrame(self.index)


class FakeFrameSource:
    def __init__(self, indices):
        self.indices = indices

    def frames(self, video_path, start_seconds, end_seconds):
        for index in self.indices:
            yield index, 25.0, FakeFrame(index)


class FakeDetector:
    def __init__(self, detections_by_frame):
        self.detections_by_frame = detections_by_frame

    def detect(self, frame, confidence, device):
        return self.detections_by_frame.get(frame.index, [])


class FakeVisionAnalyzer:
    def __init__(self, description="Descrição objetiva"):
        self.calls = []
        self.description = description

    def describe(self, frame, detections, model):
        self.calls.append((frame.index, detections, model))
        return self.description


class FirstToolReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "input.mp4"
        self.weights = self.root / "best.pt"
        self.video.touch()
        self.weights.touch()
        self.output = self.root / "reports"
        self.cv2 = SimpleNamespace(imwrite=lambda path, frame: True)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _detection(class_id=0, class_name="grasper", confidence=0.9):
        return ToolDetection(class_id, class_name, confidence, (1.0, 2.0, 30.0, 40.0))

    def _run(self, detections_by_frame, **overrides):
        defaults = dict(
            video_path=self.video,
            weights_path=self.weights,
            output_dir=self.output,
            consecutive_frames=3,
        )
        defaults.update(overrides)
        request = FirstToolReportRequest(**defaults)
        source = FakeFrameSource([10, 11, 12, 13, 14, 15])
        detector = FakeDetector(detections_by_frame)
        analyzer = FakeVisionAnalyzer()
        use_case = FirstToolReport(source, detector, analyzer)
        return use_case, analyzer, request

    def test_confirms_consecutive_detections_and_reports_first_frame(self):
        detection = self._detection()
        use_case, analyzer, request = self._run({10: [detection], 12: [detection], 13: [detection], 14: [detection]})
        saved_frames = []
        self.cv2.imwrite = lambda path, frame: saved_frames.append((path, frame.index)) or True

        with patch.dict(sys.modules, {"cv2": self.cv2}):
            result = use_case.execute(request)

        self.assertEqual(result.frame_index, 12)
        self.assertEqual(result.confirmation_frame_index, 14)
        self.assertEqual(result.timestamp_seconds, 12 / 25)
        self.assertEqual(saved_frames[0][1], 12)
        self.assertEqual(analyzer.calls, [])
        report = json.loads(result.json_path.read_text(encoding="utf-8"))
        self.assertFalse(report["vision_analysis"]["frame_sent_externally"])
        self.assertIn("## Análise visual", result.markdown_path.read_text(encoding="utf-8"))

    def test_reports_multiple_classes_confirmed_on_same_frame(self):
        grasper = self._detection(0, "grasper", 0.8)
        hook = self._detection(2, "hook", 0.95)
        use_case, _, request = self._run({
            10: [grasper, hook],
            11: [grasper, hook],
            12: [grasper, hook],
        })
        with patch.dict(sys.modules, {"cv2": self.cv2}):
            result = use_case.execute(request)
        self.assertEqual([item.detection.class_name for item in result.detections], ["grasper", "hook"])

    def test_sends_frame_only_when_explicitly_requested(self):
        detection = self._detection()
        use_case, analyzer, request = self._run(
            {10: [detection], 11: [detection], 12: [detection]},
            send_frame_to_openai=True,
        )
        with patch.dict(sys.modules, {"cv2": self.cv2}):
            result = use_case.execute(request)
        self.assertEqual(result.vision_description, "Descrição objetiva")
        self.assertEqual(analyzer.calls[0][0], 10)
        self.assertEqual(analyzer.calls[0][2], "gpt-4o")

    def test_raises_when_no_class_meets_confirmation_rule(self):
        detection = self._detection()
        use_case, _, request = self._run({10: [detection], 12: [detection], 14: [detection]})
        with self.assertRaisesRegex(RuntimeError, "Nenhuma ferramenta foi confirmada"):
            use_case.execute(request)

    def test_validates_interval_before_processing(self):
        use_case, _, request = self._run({}, start_seconds=5, end_seconds=4)
        with self.assertRaisesRegex(ValueError, "fim do trecho"):
            use_case.execute(request)


if __name__ == "__main__":
    unittest.main()
