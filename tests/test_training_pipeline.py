import json
from pathlib import Path
import tempfile
import unittest

from video_review.application.dataset import (
    _read_tracking_annotations,
    prepare_yolo_dataset,
    validate_tracking_data,
)


class DatasetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tracking = self.root / "tracking"
        self.tracking.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _add_sample(self, tool: str, class_id: int, video: str, frame: int):
        run = self.tracking / tool / f"001_{video}"
        (run / "images").mkdir(parents=True, exist_ok=True)
        (run / "labels").mkdir(exist_ok=True)
        image = run / "images" / f"frame_{frame:06d}.jpg"
        label = run / "labels" / f"frame_{frame:06d}.txt"
        image.write_bytes(b"synthetic image fixture")
        label.write_text(f"{class_id} 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    def test_validation_checks_counts_and_empty_runs(self):
        for video in ("video01", "video02", "video03"):
            self._add_sample("grasper", 0, video, 10)
        (self.tracking / "hook" / "001_video04" / "images").mkdir(parents=True)

        summary = validate_tracking_data(self.tracking)

        self.assertEqual(summary.image_count, 3)
        self.assertEqual(summary.video_count, 3)
        self.assertEqual(summary.empty_runs, 1)
        self.assertEqual(summary.class_counts["grasper"], 3)

    def test_prepare_stratifies_by_tool_without_merging_same_video_frames(self):
        for tool, class_id in (("grasper", 0), ("hook", 2)):
            for frame in range(20):
                self._add_sample(tool, class_id, "video01", frame)
        output = self.root / "dataset"
        output.mkdir()
        (output / "stale.txt").write_text("stale", encoding="utf-8")

        annotations, _ = _read_tracking_annotations(self.tracking)
        summary = prepare_yolo_dataset(self.tracking, output, seed=42)

        self.assertFalse((output / "stale.txt").exists())
        self.assertTrue((output / "data.yaml").is_file())
        self.assertEqual(summary.image_count, 40)
        self.assertEqual(len(annotations), 40)
        manifest = json.loads((output / "split_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["strategy"], "random_per_tool")
        self.assertEqual(manifest["split_image_counts"], {"train": 32, "val": 4, "test": 4})
        self.assertEqual(manifest["split_class_image_counts"]["train"]["grasper"], 16)
        self.assertEqual(manifest["split_class_image_counts"]["val"]["hook"], 2)
        self.assertEqual(
            sum(len(list((output / "images" / split).glob("*.jpg"))) for split in ("train", "val", "test")), 40
        )
        # Mesmo vídeo/frame em ferramentas distintas permanece como duas amostras independentes.
        names = [path.name for split in ("train", "val", "test") for path in (output / "images" / split).glob("*.jpg")]
        self.assertEqual(len(names), len(set(names)))

    def test_split_is_deterministic_and_requires_at_least_three_images_per_tool(self):
        for frame in range(2):
            self._add_sample("grasper", 0, "video01", frame)
        with self.assertRaisesRegex(ValueError, "menos de 3 imagens"):
            prepare_yolo_dataset(self.tracking, self.root / "dataset", seed=7)

    def test_validation_rejects_wrong_class_id(self):
        self._add_sample("hook", 1, "video01", 10)
        with self.assertRaisesRegex(ValueError, "não corresponde à pasta"):
            validate_tracking_data(self.tracking)


if __name__ == "__main__":
    unittest.main()
