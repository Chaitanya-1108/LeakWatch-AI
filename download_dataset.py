import argparse
import os
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a labeled YOLOv8 dataset from Roboflow into water-leak-yolo."
    )
    parser.add_argument("--api-key", default=os.getenv("ROBOFLOW_API_KEY", ""))
    parser.add_argument("--workspace", default=os.getenv("ROBOFLOW_WORKSPACE", ""))
    parser.add_argument("--project", default=os.getenv("ROBOFLOW_PROJECT", ""))
    parser.add_argument("--version", type=int, default=int(os.getenv("ROBOFLOW_VERSION", "0")))
    parser.add_argument(
        "--output",
        default="water-leak-yolo",
        help="Target dataset folder (YOLO format).",
    )
    return parser.parse_args()


def _count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return len(list(path.rglob(pattern)))


def _print_split_counts(dataset_root: Path) -> None:
    for split in ("train", "val", "test"):
        image_count = _count_files(dataset_root / "images" / split, "*.*")
        label_count = _count_files(dataset_root / "labels" / split, "*.txt")
        print(f"{split}: images={image_count}, labels={label_count}")


def download_from_roboflow(
    api_key: str,
    workspace: str,
    project: str,
    version: int,
    output_dir: Path,
) -> None:
    if not all([api_key, workspace, project, version > 0]):
        raise ValueError(
            "Missing Roboflow settings. Provide --api-key, --workspace, --project, --version "
            "or set ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_PROJECT, ROBOFLOW_VERSION."
        )

    try:
        from roboflow import Roboflow  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "roboflow package is not installed. Run: pip install roboflow"
        ) from exc

    rf = Roboflow(api_key=api_key)
    project_ref = rf.workspace(workspace).project(project)
    version_ref = project_ref.version(version)
    downloaded = Path(version_ref.download("yolov8").location)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.move(str(downloaded), str(output_dir))

    print(f"Downloaded labeled dataset to: {output_dir.resolve()}")
    _print_split_counts(output_dir)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)

    try:
        download_from_roboflow(
            api_key=args.api_key,
            workspace=args.workspace,
            project=args.project,
            version=args.version,
            output_dir=output_dir,
        )
    except Exception as exc:
        print(f"Dataset download failed: {exc}")
        print("")
        print("You can still run inference without training.")
        print("For custom training, you need labeled YOLO data (images + labels).")
        raise


if __name__ == "__main__":
    main()

