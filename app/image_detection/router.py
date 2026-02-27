import json
from PIL import UnidentifiedImageError

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.image_detection.models import (
    LeakImageDetectionResponse,
    LeakImagePredictionHistoryItem,
)
from app.image_detection.service import leak_image_detection_service
from app.models.db_models import LeakImagePrediction

router = APIRouter()


@router.post("/upload-leak-image", response_model=LeakImageDetectionResponse)
async def upload_leak_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        result = leak_image_detection_service.detect(image_bytes)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image file. Unable to decode image.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image detection failed: {exc}") from exc

    history_row = LeakImagePrediction(
        filename=file.filename or "uploaded_image",
        leak_type=result.leak_type,
        severity_level=result.severity_level,
        confidence_score=result.confidence_score,
        recommended_solution=result.recommended_solution,
        detections_json=result.detections_json,
    )
    db.add(history_row)
    db.commit()

    return LeakImageDetectionResponse(
        leak_type=result.leak_type,
        severity_level=result.severity_level,
        confidence_score=result.confidence_score,
        recommended_solution=result.recommended_solution,
        annotated_image_base64=result.annotated_image_base64,
        detections=result.detections,
    )


@router.get("/leak-image-history", response_model=list[LeakImagePredictionHistoryItem])
async def get_leak_image_history(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(LeakImagePrediction)
        .order_by(LeakImagePrediction.timestamp.desc())
        .limit(limit)
        .all()
    )

    # Normalize legacy/invalid rows defensively.
    history = []
    for row in rows:
        try:
            json.loads(row.detections_json)
        except Exception:
            row.detections_json = "[]"
        history.append(
            LeakImagePredictionHistoryItem(
                id=row.id,
                timestamp=row.timestamp,
                filename=row.filename,
                leak_type=row.leak_type,
                severity_level=row.severity_level,
                confidence_score=row.confidence_score,
                recommended_solution=row.recommended_solution,
            )
        )
    return history
