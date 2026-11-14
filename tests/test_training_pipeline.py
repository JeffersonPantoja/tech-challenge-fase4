import json
from pathlib import Path
import tempfile
import unittest

from video_review.application.dataset import (
    Annotation,
    _partition_temporal_blocks,
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

    def test_prepare_cleans_target_and_splits_contiguous_temporal_blocks(self):
        # Nove blocos de um mesmo vídeo devem alimentar train/val/test sem split por vídeo.
        for block in range(9):
            for offset in (0, 300, 700, 749):
                self._add_sample("grasper", 0, "video01", block * 750 + offset)
        output = self.root / "dataset"
        output.mkdir()
        (output / "stale.txt").write_text("stale", encoding="utf-8")

        summary = prepare_yolo_dataset(self.tracking, output, seed=42, block_seconds=30, gap_seconds=2)

        self.assertFalse((output / "stale.txt").exists())
        self.assertTrue((output / "data.yaml").is_file())
        self.assertLess(summary.image_count, 36)
        self.assertGreater(summary.excluded_frames, 0)
        manifest = json.loads((output / "split_manifest.json").read_text(encoding="utf-8"))
        block_splits = {block["split"] for block in manifest["videos"]["video01"]}
        self.assertEqual(block_splits, {"train", "val", "test"})
        self.assertEqual(manifest["strategy"], "temporal_blocks")
        self.assertEqual(manifest["gap_seconds"], 2)
        self.assertEqual(
            sum(len(list((output / "images" / split).glob("*.jpg"))) for split in ("train", "val", "test")),
            summary.image_count,
        )

    def test_temporal_block_split_is_deterministic_and_requires_three_blocks(self):
        annotations = [
            Annotation(Path("frame.jpg"), "video01", frame * 750, ())
            for frame in range(4)
        ]
        first = _partition_temporal_blocks(annotations, 7, 30, 2, 25)
        second = _partition_temporal_blocks(annotations, 7, 30, 2, 25)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            _partition_temporal_blocks(annotations[:2], 7, 30, 2, 25)

    def test_validation_rejects_wrong_class_id(self):
        self._add_sample("hook", 1, "video01", 10)
        with self.assertRaisesRegex(ValueError, "não corresponde à pasta"):
            validate_tracking_data(self.tracking)


if __name__ == "__main__":
    unittest.main()
