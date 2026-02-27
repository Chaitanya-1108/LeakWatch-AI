import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .models import (
    WaterQualityAssessment,
    WaterQualityAssessmentInput,
    WaterQualityPredictRequest,
    WaterQualityPredictionResponse,
    WaterQualityReading,
    WaterQualitySimulationMode,
    WaterQualityState,
    WQIResult,
)
from .service import water_quality_service
from app.database.session import get_db
from app.models.db_models import WaterQualityReadingRecord

router = APIRouter()


@router.get("/status", response_model=WaterQualityState)
async def get_status():
    return WaterQualityState(
        is_active=True,
        current_mode=water_quality_service.mode,
    )


@router.post("/mode/{mode}")
async def set_simulation_mode(mode: WaterQualitySimulationMode):
    water_quality_service.set_mode(mode)
    return {"message": f"Water quality simulation mode set to {mode}"}


@router.get("/history", response_model=list[WaterQualityPredictionResponse])
async def get_quality_history(limit: int = 100, db: Session = Depends(get_db)):
    try:
        readings: list[WaterQualityReadingRecord] = (
            db.query(WaterQualityReadingRecord)
            .order_by(WaterQualityReadingRecord.timestamp.desc())
            .limit(limit)
            .all()
        )
    except OperationalError:
        return []
    results: list[WaterQualityPredictionResponse] = []
    for row in readings:
        payload = WaterQualityAssessmentInput(
            ph=row.ph,
            turbidity=row.turbidity,
            tds=row.tds,
            temperature=row.temperature,
            dissolved_oxygen=row.dissolved_oxygen,
        )
        results.append(
            water_quality_service.predict_quality(
                payload=payload,
                pipeline_id=row.pipeline_id,
                timestamp=row.timestamp,
            )
        )
    return results


@router.get("/live", response_model=WaterQualityPredictionResponse)
async def get_live_prediction():
    reading = water_quality_service.generate_next_reading()
    payload = WaterQualityAssessmentInput(
        ph=reading.ph,
        turbidity=reading.turbidity,
        tds=reading.tds,
        temperature=reading.temperature,
        dissolved_oxygen=reading.dissolved_oxygen,
    )
    return water_quality_service.predict_quality(
        payload=payload,
        pipeline_id=reading.pipeline_id,
        timestamp=reading.timestamp,
    )


@router.get("/data", response_model=WaterQualityReading)
async def get_current_data():
    return water_quality_service.generate_next_reading()


@router.post("/assess", response_model=WaterQualityAssessment)
async def assess_water_condition(payload: WaterQualityAssessmentInput):
    return water_quality_service.assess(payload)


@router.post("/predict", response_model=WaterQualityPredictionResponse)
async def predict_water_quality(payload: WaterQualityPredictRequest):
    input_data = WaterQualityAssessmentInput(
        ph=payload.ph,
        turbidity=payload.turbidity,
        tds=payload.tds,
        temperature=payload.temperature,
        dissolved_oxygen=payload.dissolved_oxygen,
    )
    return water_quality_service.predict_quality(
        payload=input_data,
        pipeline_id=payload.pipeline_id,
    )


@router.post("/wqi", response_model=WQIResult)
async def calculate_wqi(payload: WaterQualityAssessmentInput):
    return water_quality_service.calculate_wqi(payload)


@router.get("/simulate-assess", response_model=WaterQualityAssessment)
async def simulate_and_assess():
    reading = water_quality_service.generate_next_reading()
    payload = WaterQualityAssessmentInput(
        ph=reading.ph,
        turbidity=reading.turbidity,
        tds=reading.tds,
        temperature=reading.temperature,
        dissolved_oxygen=reading.dissolved_oxygen,
    )
    return water_quality_service.assess(payload)


@router.get("/stream")
async def stream_water_quality():
    async def event_generator():
        while True:
            reading = water_quality_service.generate_next_reading()
            payload = WaterQualityAssessmentInput(
                ph=reading.ph,
                turbidity=reading.turbidity,
                tds=reading.tds,
                temperature=reading.temperature,
                dissolved_oxygen=reading.dissolved_oxygen,
            )
            assessment = water_quality_service.assess(payload)
            event = {
                "reading": reading.model_dump(),
                "assessment": assessment.model_dump(),
            }
            yield f"data: {json.dumps(event, default=str)}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/ws/live")
async def websocket_live_water_quality(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            reading = water_quality_service.generate_next_reading()
            payload = WaterQualityAssessmentInput(
                ph=reading.ph,
                turbidity=reading.turbidity,
                tds=reading.tds,
                temperature=reading.temperature,
                dissolved_oxygen=reading.dissolved_oxygen,
            )
            prediction = water_quality_service.predict_quality(
                payload=payload,
                pipeline_id=reading.pipeline_id,
                timestamp=reading.timestamp,
            )
            should_alert, reasons = water_quality_service.evaluate_alert_conditions(prediction)

            message = {
                **prediction.model_dump(mode="json"),
                "event": "WATER_QUALITY_LIVE",
                "alert_triggered": should_alert,
                "alert_reasons": reasons,
                "server_time": datetime.now().isoformat(),
            }
            await websocket.send_json(message)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
