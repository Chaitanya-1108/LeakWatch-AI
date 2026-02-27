import base64
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO


LEAK_CLASS_ALIASES = {
    "pipe_crack": "Pipe crack",
    "crack": "Pipe crack",
    "rust_corrosion": "Rust corrosion",
    "corrosion": "Rust corrosion",
    "joint_leakage": "Joint leakage",
    "joint_leak": "Joint leakage",
    "burst_pipe": "Burst pipe",
    "burst": "Burst pipe",
}

RECOMMENDED_SOLUTIONS = {
    "Pipe crack": "Apply emergency clamp, isolate section, and schedule pipe replacement.",
    "Rust corrosion": "Remove corroded section and apply anti-corrosion coating with protective wrap.",
    "Joint leakage": "Re-seal or replace faulty joint and re-test line pressure.",
    "Burst pipe": "Shut off supply immediately, replace burst section, and inspect nearby segments.",
    "No leak detected": "No immediate action required. Continue routine visual inspections.",
}


@dataclass
class DetectionSummary:
    leak_type: str
    severity_level: str
    confidence_score: float
    recommended_solution: str
    detections_json: str
    detections: list[dict[str, Any]]
    annotated_image_base64: str


class LeakImageDetectionService:
    def __init__(self) -> None:
        self.model_path = os.getenv("YOLOV8_MODEL_PATH", "yolov8n.pt")
        self.fallback_model_path = os.getenv("YOLOV8_FALLBACK_MODEL_PATH", "yolov8n.pt")
        self.conf_threshold = float(os.getenv("YOLOV8_CONF", "0.2"))
        self.iou_threshold = float(os.getenv("YOLOV8_IOU", "0.55"))
        self.imgsz = int(os.getenv("YOLOV8_IMGSZ", "960"))
        self.max_det = int(os.getenv("YOLOV8_MAX_DET", "50"))
        self.use_tta = os.getenv("YOLOV8_TTA", "false").lower() in {"1", "true", "yes"}
        self.enable_heuristic_fallback = (
            os.getenv("ENABLE_HEURISTIC_FALLBACK", "true").lower() in {"1", "true", "yes"}
        )
        self.model: YOLO | None = None
        self.logger = logging.getLogger("image_detection")

    def _get_model(self) -> YOLO:
        if self.model is None:
            primary = Path(self.model_path)
            fallback = Path(self.fallback_model_path)

            selected_path = primary
            if not primary.exists():
                if fallback.exists():
                    self.logger.warning(
                        "YOLO model not found at '%s'. Falling back to '%s'.",
                        primary,
                        fallback,
                    )
                    selected_path = fallback
                else:
                    raise FileNotFoundError(
                        f"YOLO model not found at '{primary}' and fallback '{fallback}' is also missing."
                    )

            self.model = YOLO(str(selected_path))
        return self.model

    def _model_supports_leak_classes(self, model_names: dict[int, str] | list[str] | None) -> bool:
        if not model_names:
            return False

        if isinstance(model_names, dict):
            names = list(model_names.values())
        else:
            names = list(model_names)

        for name in names:
            if self._normalize_label(str(name)):
                return True
        return False

    @staticmethod
    def _normalize_label(raw_label: str) -> str | None:
        key = raw_label.strip().lower().replace(" ", "_").replace("-", "_")
        return LEAK_CLASS_ALIASES.get(key)

    @staticmethod
    def _severity_from_detection(leak_type: str, confidence: float) -> str:
        if leak_type == "Burst pipe":
            return "Critical" if confidence >= 0.45 else "Moderate"
        if leak_type == "Pipe crack":
            return "High" if confidence >= 0.6 else "Moderate"
        if leak_type == "Rust corrosion":
            return "Moderate" if confidence >= 0.5 else "Low"
        if leak_type == "Joint leakage":
            return "Moderate" if confidence >= 0.5 else "Low"
        return "Low"

    @staticmethod
    def _encode_annotated_image(image: Image.Image, detections: list[dict[str, Any]]) -> str:
        annotated = image.copy()
        drawer = ImageDraw.Draw(annotated)

        for det in detections:
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
            label = f'{det["label"]} {det["confidence"]:.2f}'
            drawer.rectangle([(x1, y1), (x2, y2)], outline=(239, 68, 68), width=4)
            drawer.text((x1 + 4, max(2, y1 - 18)), label, fill=(255, 255, 255))

        buffer = io.BytesIO()
        annotated.save(buffer, format="JPEG", quality=90)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def _boxes_from_mask(
        mask: np.ndarray,
        label: str,
        image_area: int,
        base_confidence: float,
        min_area_ratio: float = 0.002,
        max_boxes: int = 4,
    ) -> list[dict[str, Any]]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[dict[str, Any]] = []
        min_area = image_area * min_area_ratio

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            area_ratio = area / image_area
            confidence = min(0.88, base_confidence + (area_ratio * 3.0))
            detections.append(
                {
                    "x1": round(float(x), 2),
                    "y1": round(float(y), 2),
                    "x2": round(float(x + w), 2),
                    "y2": round(float(y + h), 2),
                    "confidence": round(float(confidence), 4),
                    "label": label,
                }
            )

        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections[:max_boxes]

    def _heuristic_detect(self, image_array: np.ndarray) -> list[dict[str, Any]]:
        h, w = image_array.shape[:2]
        image_area = max(1, h * w)

        bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Rust/corrosion tones (brown-orange spectrum).
        rust_mask = cv2.inRange(hsv, np.array([5, 60, 30]), np.array([25, 255, 220]))
        rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        rust_mask = cv2.morphologyEx(rust_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        rust_dets = self._boxes_from_mask(
            rust_mask,
            label="Rust corrosion",
            image_area=image_area,
            base_confidence=0.56,
            min_area_ratio=0.0015,
        )

        # Water leakage cues (blue/cyan wet regions + reflective pools).
        water_blue = cv2.inRange(hsv, np.array([80, 35, 25]), np.array([140, 255, 255]))
        water_reflect = cv2.inRange(hsv, np.array([0, 0, 130]), np.array([180, 70, 255]))
        water_mask = cv2.bitwise_or(water_blue, water_reflect)
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        water_ratio = float(np.count_nonzero(water_mask)) / float(image_area)

        water_label = "Burst pipe" if water_ratio >= 0.12 else "Joint leakage"
        water_conf = 0.62 if water_label == "Burst pipe" else 0.54
        water_dets = self._boxes_from_mask(
            water_mask,
            label=water_label,
            image_area=image_area,
            base_confidence=water_conf,
            min_area_ratio=0.003,
        )

        # Crack cues from dark-edge structures.
        edges = cv2.Canny(gray, 80, 180)
        dark_regions = cv2.inRange(gray, 0, 55)
        crack_mask = cv2.bitwise_and(edges, dark_regions)
        crack_mask = cv2.dilate(crack_mask, np.ones((3, 3), np.uint8), iterations=1)
        crack_dets = self._boxes_from_mask(
            crack_mask,
            label="Pipe crack",
            image_area=image_area,
            base_confidence=0.53,
            min_area_ratio=0.0012,
        )

        all_dets = rust_dets + water_dets + crack_dets
        all_dets.sort(key=lambda d: d["confidence"], reverse=True)
        return all_dets[:5]

    def detect(self, image_bytes: bytes) -> DetectionSummary:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_array = np.array(image)
        model = self._get_model()
        result = None
        yolo_failed = False
        try:
            results = model.predict(
                source=image_array,
                verbose=False,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                imgsz=self.imgsz,
                max_det=self.max_det,
                augment=self.use_tta,
            )
            result = results[0]
        except Exception as exc:
            yolo_failed = True
            self.logger.exception("YOLO inference failed. Falling back to heuristic detector. Error: %s", exc)

        detections: list[dict[str, Any]] = []
        best_match: dict[str, Any] | None = None

        if result is not None:
            for box in result.boxes:
                class_id = int(box.cls.item())
                raw_label = result.names.get(class_id, str(class_id))
                normalized = self._normalize_label(raw_label)
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]

                if normalized is None:
                    continue

                det = {
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "x2": round(x2, 2),
                    "y2": round(y2, 2),
                    "confidence": round(confidence, 4),
                    "label": normalized,
                }
                detections.append(det)

                if best_match is None or confidence > best_match["confidence"]:
                    best_match = det

        # If YOLO doesn't output leak-specific classes, use CV fallback cues.
        # This is automatically enabled for generic YOLO models (e.g. yolov8n.pt)
        # even if ENABLE_HEURISTIC_FALLBACK=false, so simulation stays usable.
        has_leak_classes = self._model_supports_leak_classes(result.names if result is not None else None)
        should_use_fallback = (
            (self.enable_heuristic_fallback or not has_leak_classes or yolo_failed)
            and not detections
        )

        if should_use_fallback:
            if not has_leak_classes:
                self.logger.warning(
                    "Current YOLO model appears non-leak-specific. Using heuristic fallback for leak detection."
                )
            fallback_detections = self._heuristic_detect(image_array)
            detections.extend(fallback_detections)
            if fallback_detections:
                best_match = fallback_detections[0]

        if best_match is None:
            leak_type = "No leak detected"
            confidence_score = 0.0
            severity_level = "Low"
        else:
            leak_type = best_match["label"]
            confidence_score = best_match["confidence"]
            severity_level = self._severity_from_detection(leak_type, confidence_score)

        return DetectionSummary(
            leak_type=leak_type,
            severity_level=severity_level,
            confidence_score=round(confidence_score, 4),
            recommended_solution=RECOMMENDED_SOLUTIONS[leak_type],
            detections_json=json.dumps(detections),
            detections=detections,
            annotated_image_base64=self._encode_annotated_image(image, detections),
        )


leak_image_detection_service = LeakImageDetectionService()
