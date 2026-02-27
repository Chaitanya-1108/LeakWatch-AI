from datetime import datetime
from pydantic import BaseModel


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    label: str


class LeakImageDetectionResponse(BaseModel):
    leak_type: str
    severity_level: str
    confidence_score: float
    recommended_solution: str
    annotated_image_base64: str
    detections: list[BoundingBox]


class LeakImagePredictionHistoryItem(BaseModel):
    id: int
    timestamp: datetime
    filename: str
    leak_type: str
    severity_level: str
    confidence_score: float
    recommended_solution: str

