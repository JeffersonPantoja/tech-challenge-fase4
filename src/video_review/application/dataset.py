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
    tracking_run: str
    tool_class: str
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

    rows: list[Annotation] = []
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

                labels: set[str] = set()
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
                    labels.add(" ".join(parts))

                rows.append(Annotation(
                    image_path=image_path,
                    tracking_run=run_dir.name,
                    tool_class=class_dir.name,
                    source_video=video_id,
                    frame_index=frame_index,
                    labels=tuple(sorted(labels)),
                ))

    return rows, empty_runs


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


def _allocate_split_counts(total: int, ratios: dict[str, float]) -> dict[str, int]:
    exact = {name: total * ratio for name, ratio in ratios.items()}
    counts = {name: math.floor(value) for name, value in exact.items()}
    remaining = total - sum(counts.values())
    for name in sorted(exact, key=lambda key: (-(exact[key] - counts[key]), tuple(ratios).index(key))):
        if remaining == 0:
            break
        counts[name] += 1
        remaining -= 1
    if total >= 3 and any(counts[name] == 0 for name in counts):
        raise ValueError("Cada ferramenta precisa ter ao menos 3 imagens para preencher treino, validação e teste.")
    return counts


def _stratified_random_split(
    annotations: list[Annotation], seed: int, ratios: dict[str, float]
) -> dict[Path, str]:
    """Sorteia imagens separadamente por ferramenta/rastreamento, sem fundir frames."""
    grouped: dict[str, list[Annotation]] = {}
    for annotation in annotations:
        grouped.setdefault(annotation.tool_class, []).append(annotation)
    rng = random.Random(seed)
    assignments: dict[Path, str] = {}
    for tool_class, samples in sorted(grouped.items()):
        if len(samples) < 3:
            raise ValueError(f"A ferramenta {tool_class} tem menos de 3 imagens e não pode preencher as 3 partições.")
        rng.shuffle(samples)
        counts = _allocate_split_counts(len(samples), ratios)
        cursor = 0
        for split in ratios:
            for sample in samples[cursor:cursor + counts[split]]:
                assignments[sample.image_path] = split
            cursor += counts[split]
    return assignments


def prepare_yolo_dataset(
    tracking_root: Path,
    output_dir: Path,
    seed: int = 42,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
) -> DatasetSummary:
    """Recria output_dir com imagens sorteadas por ferramenta em 80/10/10."""
    annotations, empty_runs = _read_tracking_annotations(tracking_root)
    if not annotations:
        raise ValueError(f"Nenhuma imagem anotada encontrada em {tracking_root}")
    output_dir = output_dir.expanduser().resolve()
    tracking_root = tracking_root.expanduser().resolve()
    if output_dir == tracking_root or output_dir in tracking_root.parents or tracking_root in output_dir.parents:
        raise ValueError("A pasta de saída não pode ser a pasta de rastreamentos nem conter/estar dentro dela.")
    if output_dir == Path(output_dir.anchor) or output_dir == Path.home().resolve():
        raise ValueError(f"Destino inseguro para recriação: {output_dir}")

    ratios = {"train": train_ratio, "val": val_ratio, "test": test_ratio}
    if any(value <= 0 for value in ratios.values()) or not math.isclose(sum(ratios.values()), 1.0, abs_tol=1e-8):
        raise ValueError("As proporções de treino, validação e teste devem ser positivas e somar 1.0.")
    split_by_image = _stratified_random_split(annotations, seed, ratios)

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
    split_class_counts = {split: {name: 0 for name in TOOL_CLASSES} for split in split_counts}
    image_manifest = {split: [] for split in split_counts}
    for annotation in annotations:
        split = split_by_image[annotation.image_path]
        split_counts[split] += 1
        base_name = f"{annotation.tool_class}_{annotation.tracking_run}_frame_{annotation.frame_index:06d}"
        shutil.copy2(annotation.image_path, output_dir / "images" / split / f"{base_name}.jpg")
        label_file = output_dir / "labels" / split / f"{base_name}.txt"
        label_file.write_text("\n".join(annotation.labels) + ("\n" if annotation.labels else ""), encoding="utf-8")
        for label in annotation.labels:
            class_name = TOOL_CLASSES[int(label.split()[0])]
            class_counts[class_name] += 1
            split_class_counts[split][class_name] += 1
        image_manifest[split].append({
            "tool": annotation.tool_class,
            "tracking_run": annotation.tracking_run,
            "video": annotation.source_video,
            "frame": annotation.frame_index,
            "filename": f"{base_name}.jpg",
        })

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
                "strategy": "random_per_tool",
                "seed": seed,
                "ratios": {"train": train_ratio, "val": val_ratio, "test": test_ratio},
                "split_image_counts": split_counts,
                "split_class_image_counts": split_class_counts,
                "images": image_manifest,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    return DatasetSummary(
        image_count=len(annotations),
        video_count=len({item.source_video for item in annotations}),
        empty_runs=empty_runs,
        class_counts=class_counts,
    )
