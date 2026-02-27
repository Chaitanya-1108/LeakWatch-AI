import argparse
import random
import shutil
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import YOLO image+label pairs into water-leak-yolo train/val/test folders."
    )
    parser.add_argument(
        "--source-images",
        required=True,
        help="Folder containing source images.",
    )
    parser.add_argument(
        "--source-labels",
        required=True,
        help="Folder containing source YOLO .txt labels with matching filenames.",
    )
    parser.add_argument(
        "--target-root",
        default="water-leak-yolo",
        help="Target dataset root.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clear-target",
        action="store_true",
        help="Delete target images/labels splits before import.",
    )
    return parser.parse_args()


def ensure_split_dirs(root: Path) -> None:
    for split in ("train", "val", "test"):
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)


def clear_split_dirs(root: Path) -> None:
    for base in ("images", "labels"):
        for split in ("train", "val", "test"):
            d = root / base / split
            if d.exists():
                shutil.rmtree(d)


def discover_pairs(images_dir: Path, labels_dir: Path) -> list[tuple[Path, Path]]:
    image_files = [p for p in images_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    pairs: list[tuple[Path, Path]] = []

    missing_labels = 0
    for image_path in image_files:
        label_path = labels_dir / f"{image_path.stem}.txt"
        if label_path.exists():
            pairs.append((image_path, label_path))
        else:
            missing_labels += 1

    print(f"Found images: {len(image_files)}")
    print(f"Matched image+label pairs: {len(pairs)}")
    print(f"Images skipped (missing label): {missing_labels}")
    return pairs


def split_pairs(
    pairs: list[tuple[Path, Path]],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict[str, list[tuple[Path, Path]]]:
    total = train_ratio + val_ratio + test_ratio
    if total <= 0:
        raise ValueError("Ratios must sum to > 0")
    train_ratio /= total
    val_ratio /= total
    test_ratio /= total

    random.Random(seed).shuffle(pairs)
    n = len(pairs)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val

    return {
        "train": pairs[:n_train],
        "val": pairs[n_train:n_train + n_val],
        "test": pairs[n_train + n_val:n_train + n_val + n_test],
    }


def copy_split(split: str, items: list[tuple[Path, Path]], target_root: Path) -> None:
    for image_path, label_path in items:
        shutil.copy2(image_path, target_root / "images" / split / image_path.name)
        shutil.copy2(label_path, target_root / "labels" / split / label_path.name)


def main() -> None:
    args = parse_args()
    src_images = Path(args.source_images)
    src_labels = Path(args.source_labels)
    target_root = Path(args.target_root)

    if not src_images.exists():
        raise FileNotFoundError(f"source-images not found: {src_images}")
    if not src_labels.exists():
        raise FileNotFoundError(f"source-labels not found: {src_labels}")

    if args.clear_target:
        clear_split_dirs(target_root)
    ensure_split_dirs(target_root)

    pairs = discover_pairs(src_images, src_labels)
    if not pairs:
        raise SystemExit("No image+label pairs found. Nothing imported.")

    split_map = split_pairs(
        pairs=pairs,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    for split, items in split_map.items():
        copy_split(split, items, target_root)
        print(f"{split}: imported {len(items)} pairs")

    print(f"Import complete -> {target_root.resolve()}")


if __name__ == "__main__":
    main()

