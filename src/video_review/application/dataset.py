"""Validação e preparação de datasets YOLO a partir dos rastreamentos revisados."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random
import re
import shutil
import json

from video_review.application.track_video import TOOL_CLASSES


@dataclass(frozen=True)
class Annotation:
    image_path: Path
    source_video: str
    frame_index: int
    labels: tuple[str, ...]


@dataclass(frozen=True)
class DatasetSummary:
    image_count: int
    video_count: int
    empty_runs: int
    class_counts: dict[str, int]
    excluded_frames: int = 0


def _read_tracking_annotations(tracking_root: Path) -> tuple[list[Annotation], int]:
    if not tracking_root.is_dir():
        raise FileNotFoundError(f"Pasta de rastreamentos não encontrada: {tracking_root}")

    rows: dict[tuple[str, int], dict[str, object]] = {}
    empty_runs = 0
    class_ids = {name: index for index, name in enumerate(TOOL_CLASSES)}

    for class_dir in sorted(path for path in tracking_root.iterdir() if path.is_dir()):
        if class_dir.name not in class_ids:
            continue
        expected_id = class_ids[class_dir.name]
        for run_dir in sorted(path for path in class_dir.iterdir() if path.is_dir()):
            image_dir = run_dir / "images"
            label_dir = run_dir / "labels"
            images = sorted(image_dir.glob("*.jpg")) if image_dir.is_dir() else []
            if not images:
                empty_runs += 1
                continue
            if not label_dir.is_dir():
                raise ValueError(f"Pasta de labels ausente: {label_dir}")
            image_stems = {path.stem for path in images}
            label_stems = {path.stem for path in label_dir.glob("*.txt")}
            orphan_labels = label_stems - image_stems
            if orphan_labels:
                example = sorted(orphan_labels)[0]
                raise ValueError(f"Label sem imagem correspondente: {label_dir / (example + '.txt')}")

            video_match = re.search(r"(video\d+)$", run_dir.name)
            if not video_match:
                raise ValueError(f"Não foi possível determinar o vídeo de origem: {run_dir}")
            video_id = video_match.group(1)

            for image_path in images:
                frame_match = re.fullmatch(r"frame_(\d+)", image_path.stem)
                if not frame_match:
                    raise ValueError(f"Nome de frame inesperado: {image_path.name}")
                frame_index = int(frame_match.group(1))
                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.is_file():
                    raise ValueError(f"Label correspondente não encontrado: {label_path}")

                row_key = (video_id, frame_index)
                if row_key not in rows:
                    rows[row_key] = {"image_path": image_path, "labels": set()}
                elif image_path.read_bytes() != rows[row_key]["image_path"].read_bytes():
                    raise ValueError(f"Frames duplicados divergentes para {video_id}, frame {frame_index}")

                for line_number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
                    parts = line.split()
                    if len(parts) != 5:
                        raise ValueError(f"Label deve ter 5 campos: {label_path}:{line_number}")
                    if parts[0] != str(expected_id):
                        raise ValueError(
                            f"ID {parts[0]} não corresponde à pasta {class_dir.name} "
                            f"(esperado {expected_id}): {label_path}:{line_number}"
                        )
                    try:
                        coordinates = [float(value) for value in parts[1:]]
                    except ValueError as error:
                        raise ValueError(f"Coordenada não numérica: {label_path}:{line_number}") from error
                    if not all(math.isfinite(value) and 0 <= value <= 1 for value in coordinates):
                        raise ValueError(f"Coordenadas fora do intervalo [0, 1]: {label_path}:{line_number}")
                    rows[row_key]["labels"].add(" ".join(parts))

    annotations = [
        Annotation(image_path=value["image_path"], source_video=video_id, frame_index=frame_index,
                   labels=tuple(sorted(value["labels"])))
        for (video_id, frame_index), value in sorted(rows.items())
    ]
    return annotations, empty_runs


def validate_tracking_data(tracking_root: Path) -> DatasetSummary:
    annotations, empty_runs = _read_tracking_annotations(tracking_root)
    if not annotations:
        raise ValueError(f"Nenhuma imagem anotada encontrada em {tracking_root}")
    counts = {name: 0 for name in TOOL_CLASSES}
    for annotation in annotations:
        for label in annotation.labels:
            class_id = int(label.split()[0])
            counts[TOOL_CLASSES[class_id]] += 1
    return DatasetSummary(
        image_count=len(annotations),
        video_count=len({annotation.source_video for annotation in annotations}),
        empty_runs=empty_runs,
        class_counts=counts,
    )


def _partition_temporal_blocks(
    annotations: list[Annotation],
    seed: int,
    block_seconds: float,
    gap_seconds: float,
    fps: float,
) -> tuple[dict[tuple[str, int], str], set[tuple[str, int]], dict[str, list[dict[str, object]]]]:
    if block_seconds <= 0 or fps <= 0:
        raise ValueError("A duração do bloco e o FPS precisam ser positivos.")
    if gap_seconds < 0 or gap_seconds >= block_seconds:
        raise ValueError("A lacuna deve ser maior ou igual a zero e menor que a duração do bloco.")

    block_frames = max(1, round(block_seconds * fps))
    gap_frames = round(gap_seconds * fps)
    rows_by_block: dict[tuple[str, int], list[Annotation]] = {}
    for annotation in annotations:
        block_index = annotation.frame_index // block_frames
        rows_by_block.setdefault((annotation.source_video, block_index), []).append(annotation)

    blocks = sorted(rows_by_block)
    if len(blocks) < 3:
        raise ValueError(
            f"Foram encontrados apenas {len(blocks)} blocos temporais ocupados. "
            "São necessários ao menos 3; diminua --block-seconds."
        )

    rng = random.Random(seed)
    shuffled = list(blocks)
    rng.shuffle(shuffled)
    # Mantém blocos inteiros e busca aproximar 70/15/15 pelo número de imagens,
    # não apenas pela quantidade de blocos (que podem ter densidades diferentes).
    shuffled.sort(key=lambda key: -len(rows_by_block[key]))
    split_names = ("train", "val", "test")
    total_images = sum(len(items) for items in rows_by_block.values())
    targets = {"train": total_images * 0.70, "val": total_images * 0.15, "test": total_images * 0.15}
    assigned_counts = {split: 0 for split in split_names}
    split_by_block: dict[tuple[str, int], str] = {}
    for index, block_key in enumerate(shuffled):
        weight = len(rows_by_block[block_key])
        if index < len(split_names):
            split = split_names[index]
        else:
            def imbalance(candidate: str) -> float:
                return sum(
                    abs((assigned_counts[name] + (weight if name == candidate else 0) - targets[name]) / targets[name])
                    for name in split_names
                )
            split = min(split_names, key=lambda name: (imbalance(name), split_names.index(name)))
        split_by_block[block_key] = split
        assigned_counts[split] += weight

    excluded: set[tuple[str, int]] = set()
    blocks_by_video: dict[str, list[tuple[str, int]]] = {}
    for block_key in blocks:
        blocks_by_video.setdefault(block_key[0], []).append(block_key)
    if gap_frames:
        for video_id, video_blocks in blocks_by_video.items():
            for previous, following in zip(video_blocks, video_blocks[1:]):
                if split_by_block[previous] == split_by_block[following]:
                    continue
                previous_end = max(item.frame_index for item in rows_by_block[previous])
                following_start = min(item.frame_index for item in rows_by_block[following])
                midpoint = (previous_end + following_start) / 2
                for block_key in (previous, following):
                    for annotation in rows_by_block[block_key]:
                        if abs(annotation.frame_index - midpoint) < gap_frames / 2:
                            excluded.add((video_id, annotation.frame_index))

    manifest: dict[str, list[dict[str, object]]] = {}
    for video_id, video_blocks in sorted(blocks_by_video.items()):
        manifest[video_id] = []
        for _, block_index in video_blocks:
            block_annotations = rows_by_block[(video_id, block_index)]
            manifest[video_id].append({
                "block_index": block_index,
                "start_frame": block_index * block_frames,
                "end_frame_exclusive": (block_index + 1) * block_frames,
                "start_seconds": round(block_index * block_seconds, 3),
                "end_seconds": round((block_index + 1) * block_seconds, 3),
                "first_annotated_frame": min(item.frame_index for item in block_annotations),
                "last_annotated_frame": max(item.frame_index for item in block_annotations),
                "split": split_by_block[(video_id, block_index)],
            })
    return split_by_block, excluded, manifest


def prepare_yolo_dataset(
    tracking_root: Path,
    output_dir: Path,
    seed: int = 42,
    block_seconds: float = 30.0,
    gap_seconds: float = 2.0,
    fps: float = 25.0,
) -> DatasetSummary:
    """Valida fontes e recria output_dir com partições de blocos temporais."""
    annotations, empty_runs = _read_tracking_annotations(tracking_root)
    if not annotations:
        raise ValueError(f"Nenhuma imagem anotada encontrada em {tracking_root}")
    output_dir = output_dir.expanduser().resolve()
    tracking_root = tracking_root.expanduser().resolve()
    if output_dir == tracking_root or output_dir in tracking_root.parents or tracking_root in output_dir.parents:
        raise ValueError("A pasta de saída não pode ser a pasta de rastreamentos nem conter/estar dentro dela.")
    if output_dir == Path(output_dir.anchor) or output_dir == Path.home().resolve():
        raise ValueError(f"Destino inseguro para recriação: {output_dir}")

    split_by_block, excluded_frames, temporal_manifest = _partition_temporal_blocks(
        annotations, seed, block_seconds, gap_seconds, fps
    )
    retained_annotations = [
        annotation for annotation in annotations
        if (annotation.source_video, annotation.frame_index) not in excluded_frames
    ]
    present_splits = {
        split_by_block[(item.source_video, item.frame_index // max(1, round(block_seconds * fps)))]
        for item in retained_annotations
    }
    if present_splits != {"train", "val", "test"}:
        raise ValueError(
            "A lacuna temporal removeu todos os frames de uma partição. "
            "Reduza --gap-seconds ou --block-seconds e tente novamente."
        )

    # A solicitação exige uma preparação limpa: removemos apenas o destino exato informado.
    if output_dir.exists():
        if output_dir.is_dir():
            shutil.rmtree(output_dir)
        else:
            output_dir.unlink()

    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    class_counts = {name: 0 for name in TOOL_CLASSES}
    split_counts = {"train": 0, "val": 0, "test": 0}
    excluded_by_video: dict[str, list[int]] = {}
    for video_id, frame_index in sorted(excluded_frames):
        excluded_by_video.setdefault(video_id, []).append(frame_index)

    for annotation in retained_annotations:
        block_key = (
            annotation.source_video,
            annotation.frame_index // max(1, round(block_seconds * fps)),
        )
        split = split_by_block[block_key]
        split_counts[split] += 1
        base_name = f"{annotation.source_video}_frame_{annotation.frame_index:06d}"
        shutil.copy2(annotation.image_path, output_dir / "images" / split / f"{base_name}.jpg")
        label_file = output_dir / "labels" / split / f"{base_name}.txt"
        label_file.write_text("\n".join(annotation.labels) + ("\n" if annotation.labels else ""), encoding="utf-8")
        for label in annotation.labels:
            class_counts[TOOL_CLASSES[int(label.split()[0])]] += 1

    yaml_lines = [
        f"path: {output_dir.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    yaml_lines.extend(f"  {index}: {name}" for index, name in enumerate(TOOL_CLASSES))
    (output_dir / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    (output_dir / "split_manifest.json").write_text(
        json.dumps(
            {
                "strategy": "temporal_blocks",
                "seed": seed,
                "fps": fps,
                "block_seconds": block_seconds,
                "gap_seconds": gap_seconds,
                "split_image_counts": split_counts,
                "videos": temporal_manifest,
                "excluded_frames_near_split_boundaries": excluded_by_video,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    return DatasetSummary(
        image_count=len(retained_annotations),
        video_count=len({item.source_video for item in retained_annotations}),
        empty_runs=empty_runs,
        class_counts=class_counts,
        excluded_frames=len(excluded_frames),
    )
