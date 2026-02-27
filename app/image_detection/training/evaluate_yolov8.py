import argparse

from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate YOLOv8 leak model.")
    parser.add_argument("--model", type=str, required=True, help="Path to trained best.pt.")
    parser.add_argument("--data", type=str, required=True, help="Path to dataset yaml.")
    parser.add_argument("--imgsz", type=int, default=1280, help="Image size for validation.")
    parser.add_argument("--device", type=str, default="0", help="CUDA device id, or cpu.")
    parser.add_argument("--conf", type=float, default=0.2, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.55, help="IoU threshold.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model = YOLO(args.model)
    metrics = model.val(
        data=args.data,
        imgsz=args.imgsz,
        device=args.device,
        conf=args.conf,
        iou=args.iou,
    )

    print("Validation summary")
    print(f"mAP50: {metrics.box.map50:.4f}")
    print(f"mAP50-95: {metrics.box.map:.4f}")
    print(f"Precision: {metrics.box.mp:.4f}")
    print(f"Recall: {metrics.box.mr:.4f}")


if __name__ == "__main__":
    main()

