import argparse
from pathlib import Path


VALID_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate YOLO dataset structure, image/label pairing, and label syntax."
    )
    parser.add_argument(
        "--dataset-root",
        type=str,
        default="water-leak-yolo",
        help="Path to YOLO dataset root containing images/ and labels/ folders.",
    )
    parser.add_argument(
        "--num-classes",
        type=int,
        default=4,
        help="Expected number of classes (for class-id range checks).",
    )
    return parser.parse_args()


def _list_images(folder: Path) -> dict[str, Path]:
    images: dict[str, Path] = {}
    if not folder.exists():
        return images
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in VALID_IMAGE_EXTS:
            images[p.stem] = p
    return images


def _list_labels(folder: Path) -> dict[str, Path]:
    labels: dict[str, Path] = {}
    if not folder.exists():
        return labels
    for p in folder.rglob("*.txt"):
        if p.is_file():
            labels[p.stem] = p
    return labels


def _validate_label_file(path: Path, num_classes: int) -> list[str]:
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"{path}:{i} expected 5 values, found {len(parts)}")
            continue

        try:
            class_id = int(float(parts[0]))
            x = float(parts[1])
            y = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
        except ValueError:
            errors.append(f"{path}:{i} has non-numeric values")
            continue

        if class_id < 0 or class_id >= num_classes:
            errors.append(f"{path}:{i} class_id {class_id} out of range [0, {num_classes - 1}]")

        for name, value in (("x", x), ("y", y), ("w", w), ("h", h)):
            if value < 0 or value > 1:
                errors.append(f"{path}:{i} {name}={value} out of [0,1] range")

        if w <= 0 or h <= 0:
            errors.append(f"{path}:{i} width/height must be > 0")

    return errors


def validate_split(dataset_root: Path, split: str, num_classes: int) -> dict:
    img_dir = dataset_root / "images" / split
    lbl_dir = dataset_root / "labels" / split
    images = _list_images(img_dir)
    labels = _list_labels(lbl_dir)

    missing_labels = sorted(set(images.keys()) - set(labels.keys()))
    missing_images = sorted(set(labels.keys()) - set(images.keys()))

    syntax_errors: list[str] = []
    for stem in sorted(set(images.keys()) & set(labels.keys())):
        syntax_errors.extend(_validate_label_file(labels[stem], num_classes))

    return {
        "split": split,
        "image_count": len(images),
        "label_count": len(labels),
        "missing_labels": missing_labels,
        "missing_images": missing_images,
        "syntax_errors": syntax_errors,
    }


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset_root)

    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")

    all_results = [validate_split(dataset_root, s, args.num_classes) for s in ("train", "val", "test")]

    total_issues = 0
    empty_split_issues = 0
    print(f"Dataset root: {dataset_root.resolve()}")
    for r in all_results:
        print(
            f"[{r['split']}] images={r['image_count']} labels={r['label_count']} "
            f"missing_labels={len(r['missing_labels'])} missing_images={len(r['missing_images'])} "
            f"syntax_errors={len(r['syntax_errors'])}"
        )
        total_issues += len(r["missing_labels"]) + len(r["missing_images"]) + len(r["syntax_errors"])

        if r["missing_labels"][:5]:
            print(f"  sample missing labels: {r['missing_labels'][:5]}")
        if r["missing_images"][:5]:
            print(f"  sample missing images: {r['missing_images'][:5]}")
        if r["syntax_errors"][:5]:
            print(f"  sample label errors: {r['syntax_errors'][:5]}")
        if r["image_count"] == 0:
            empty_split_issues += 1
            print(f"  error: split '{r['split']}' has zero images")

    total_issues += empty_split_issues

    if total_issues == 0:
        print("Validation passed: dataset looks ready for YOLO training.")
    else:
        print(f"Validation failed: found {total_issues} issue(s). Fix these before training.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
