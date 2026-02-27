from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.db_models import LeakAlert, LeakImagePrediction
from app.simulation.service import simulator_engine
from app.water_quality.models import WaterQualityAssessmentInput, WaterCondition
from app.water_quality.service import water_quality_service

router = APIRouter()


def _leak_module_health(db: Session) -> dict:
    recent_cutoff = datetime.now() - timedelta(minutes=10)
    latest_alert = (
        db.query(LeakAlert)
        .order_by(LeakAlert.timestamp.desc())
        .first()
    )

    if latest_alert and latest_alert.timestamp >= recent_cutoff:
        severity = (latest_alert.severity or "").lower()
        if severity == "critical":
            status = "CRITICAL"
            score = 20.0
        elif severity == "moderate":
            status = "DEGRADED"
            score = 45.0
        else:
            status = "WARNING"
            score = 60.0
        details = latest_alert.analysis or "Leak event detected by simulation pipeline."
        last_event = latest_alert.timestamp.isoformat()
    else:
        status = "HEALTHY"
        score = 92.0 if simulator_engine.mode.value == "normal" else 70.0
        details = (
            "No recent leak alerts in last 10 minutes."
            if simulator_engine.mode.value == "normal"
            else f"Simulation mode is {simulator_engine.mode.value}."
        )
        last_event = None

    return {
        "status": status,
        "health_score": score,
        "simulation_mode": simulator_engine.mode.value,
        "last_event": last_event,
        "details": details,
    }


def _image_module_health(db: Session) -> dict:
    latest = (
        db.query(LeakImagePrediction)
        .order_by(LeakImagePrediction.timestamp.desc())
        .first()
    )

    if not latest:
        return {
            "status": "MONITORING",
            "health_score": 80.0,
            "details": "No uploaded inspection images yet. Module is active in simulation mode.",
            "last_prediction": None,
        }

    severity = (latest.severity_level or "").lower()
    if severity in {"critical", "high"}:
        status = "ALERT"
        score = 35.0
    elif severity == "moderate":
        status = "DEGRADED"
        score = 55.0
    else:
        status = "HEALTHY"
        score = 85.0

    return {
        "status": status,
        "health_score": score,
        "details": latest.recommended_solution,
        "last_prediction": {
            "timestamp": latest.timestamp.isoformat(),
            "leak_type": latest.leak_type,
            "severity": latest.severity_level,
            "confidence": latest.confidence_score,
        },
    }


def _water_quality_module_health() -> dict:
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

    score_map = {
        WaterCondition.SAFE: 90.0,
        WaterCondition.MODERATE: 65.0,
        WaterCondition.CONTAMINATED: 40.0,
        WaterCondition.DANGEROUS: 15.0,
    }
    status_map = {
        WaterCondition.SAFE: "HEALTHY",
        WaterCondition.MODERATE: "WATCH",
        WaterCondition.CONTAMINATED: "ALERT",
        WaterCondition.DANGEROUS: "CRITICAL",
    }

    return {
        "status": status_map[prediction.ai_prediction],
        "health_score": score_map[prediction.ai_prediction],
        "pipeline_id": prediction.pipeline_id,
        "ai_prediction": prediction.ai_prediction.value,
        "wqi_score": prediction.wqi_score,
        "risk_level": prediction.risk_level.value,
        "sensor_values": prediction.sensor_values.model_dump(),
    }


@router.get("/health")
async def get_unified_infrastructure_health(db: Session = Depends(get_db)):
    leak = _leak_module_health(db)
    image = _image_module_health(db)
    water = _water_quality_module_health()

    module_scores = [leak["health_score"], image["health_score"], water["health_score"]]
    overall_score = round(sum(module_scores) / len(module_scores), 2)

    if overall_score >= 85:
        overall_status = "HEALTHY"
    elif overall_score >= 65:
        overall_status = "WATCH"
    elif overall_score >= 40:
        overall_status = "DEGRADED"
    else:
        overall_status = "CRITICAL"

    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall_status,
        "overall_health_score": overall_score,
        "data_source": "simulated",
        "hardware_required": False,
        "modules": {
            "leak_detection": leak,
            "image_detection": image,
            "water_quality_prediction": water,
        },
    }

