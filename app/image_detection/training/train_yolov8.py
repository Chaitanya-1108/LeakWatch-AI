import argparse
from pathlib import Path

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 for leak-image detection.")
    parser.add_argument("--data", type=str, required=True, help="Path to dataset yaml.")
    parser.add_argument("--model", type=str, default="yolov8x.pt", help="Base model checkpoint.")
    parser.add_argument("--epochs", type=int, default=120, help="Training epochs.")
    parser.add_argument("--imgsz", type=int, default=1280, help="Image size.")
    parser.add_argument("--batch", type=int, default=8, help="Batch size.")
    parser.add_argument("--device", type=str, default="0", help="CUDA device id, or cpu.")
    parser.add_argument("--project", type=str, default="runs/leak_train", help="Project folder.")
    parser.add_argument("--name", type=str, default="leak_yolov8x", help="Run name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset yaml not found: {data_path}")

    model = YOLO(args.model)
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        pretrained=True,
        optimizer="AdamW",
        cos_lr=True,
        lr0=5e-4,
        lrf=1e-3,
        weight_decay=5e-4,
        patience=30,
        close_mosaic=10,
        amp=True,
        cache=True,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,
        translate=0.08,
        scale=0.25,
        shear=2.0,
        perspective=0.0005,
        flipud=0.0,
        fliplr=0.5,
        copy_paste=0.15,
        mixup=0.1,
    )


if __name__ == "__main__":
    main()

