from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import csv
import io
import json
from app.database.session import get_db
from app.models.db_models import LeakAlert, SensorReading

router = APIRouter()

def _compute_summary(db: Session) -> dict:
    # 1. Total incidents in last 30 days
    last_30_days = datetime.now() - timedelta(days=30)
    total_alerts = db.query(LeakAlert).filter(LeakAlert.timestamp >= last_30_days).count()
    
    # 2. Critical incidents
    critical_alerts = db.query(LeakAlert).filter(
        LeakAlert.timestamp >= last_30_days,
        LeakAlert.severity == "Critical"
    ).count()

    # 3. Estimated Water Loss (Aggregated)
    # Calculation logic: sum (flow_rate - baseline) for intervals where mode != normal
    # For simulation purposes, we'll assume baseline is 100 L/min
    baseline_flow = 100.0
    readings = db.query(SensorReading).filter(
        SensorReading.timestamp >= last_30_days,
        SensorReading.mode != "normal"
    ).all()
    
    total_loss_liters = 0.0
    for r in readings:
        if r.mode == "major_burst":
            # In major burst, flow rate might drop below 100 downstream, but the loss is likely much higher at the source.
            # For the sake of a cool demo, let's assume loss is based on the burst flow spike.
            loss = max(0, r.flow_rate - (baseline_flow * 0.2)) # Adjusted logic for simulation
        else:
            loss = max(0, r.flow_rate - baseline_flow)
        
        # Each reading represents 1 second in our simulation loop
        total_loss_liters += (loss / 60) # Conversion from L/min to L/sec
    
    # 4. Estimated Financial Loss (e.g., $1.50 per 1000 liters)
    cost_per_liter = 0.0015
    financial_loss = total_loss_liters * cost_per_liter

    return {
        "total_incidents": total_alerts,
        "critical_incidents": critical_alerts,
        "total_water_loss_liters": round(total_loss_liters, 2),
        "total_financial_loss_usd": round(financial_loss, 2),
        "avg_severity_score": round(float(db.query(func.avg(LeakAlert.severity_score)).scalar() or 0.0), 1),
    }


@router.get("/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Get top-level metrics for the infrastructure dashboard.
    """
    return {"summary": _compute_summary(db)}


@router.get("/export/monthly-summary")
async def export_monthly_summary(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    summary = _compute_summary(db)
    filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)
        content = buffer.getvalue()
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=monthly_summary_{filename_ts}.csv"
            },
        )

    content = json.dumps({"summary": summary}, indent=2)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=monthly_summary_{filename_ts}.json"
        },
    )


@router.get("/export/telemetry")
async def export_telemetry_data(
    days: int = Query(default=30, ge=1, le=365),
    format: str = Query(default="csv", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    start_date = datetime.now() - timedelta(days=days)
    rows = (
        db.query(SensorReading)
        .filter(SensorReading.timestamp >= start_date)
        .order_by(SensorReading.timestamp.asc())
        .all()
    )

    records = [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "pressure": r.pressure,
            "flow_rate": r.flow_rate,
            "acoustic_signal": r.acoustic_signal,
            "mode": r.mode,
        }
        for r in rows
    ]
    filename_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        content = json.dumps({"records": records, "count": len(records), "days": days}, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=telemetry_{days}d_{filename_ts}.json"
            },
        )

    buffer = io.StringIO()
    fieldnames = ["id", "timestamp", "pressure", "flow_rate", "acoustic_signal", "mode"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    content = buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=telemetry_{days}d_{filename_ts}.csv"
        },
    )

@router.get("/trends")
async def get_incident_trends(days: int = 7, db: Session = Depends(get_db)):
    """
    Get alert counts over time for charting.
    """
    # SQLite-specific date grouping (adjust if using PostgreSQL)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Group by day
    results = db.query(
        func.strftime("%Y-%m-%d", LeakAlert.timestamp).label("date"),
        func.count(LeakAlert.id).label("count")
    ).filter(LeakAlert.timestamp >= start_date)\
     .group_by("date")\
     .order_by("date")\
     .all()
    
    return [
        {"timestamp": r.date, "incidents": r.count}
        for r in results
    ]

@router.get("/sensor-stats")
async def get_sensor_stats(db: Session = Depends(get_db)):
    """
    Detailed distribution of sensor values.
    """
    stats = db.query(
        func.avg(SensorReading.pressure).label("avg_p"),
        func.max(SensorReading.pressure).label("max_p"),
        func.avg(SensorReading.flow_rate).label("avg_f"),
        func.max(SensorReading.flow_rate).label("max_f")
    ).first()
    
    return {
        "pressure": {"avg": round(stats.avg_p or 0, 2), "max": round(stats.max_p or 0, 2)},
        "flow": {"avg": round(stats.avg_f or 0, 2), "max": round(stats.max_f or 0, 2)}
    }

@router.get("/risk-assessment")
async def get_risk_assessment(db: Session = Depends(get_db)):
    """
    Calculate a risk score for each network segment based on historical reliability.
    """
    # Define segments
    segments = [("Tank", "A"), ("A", "B"), ("A", "C"), ("C", "D")]
    risk_data = {}

    for u, v in segments:
        segment_id = f"{u}-{v}"
        
        # Count historical alerts for this specifically localized segment
        # Filter by location string in SQLite
        alert_count = db.query(LeakAlert).filter(
            LeakAlert.location.contains(u),
            LeakAlert.location.contains(v)
        ).count()

        # Risk Score = (Count * 25) + (Base Risk)
        # In real world, we'd look at pipe age, material, etc.
        score = min(100, (alert_count * 25) + 10) # 10 is base risk
        
        status = "Safe"
        if score > 70: status = "Critical"
        elif score > 40: status = "Warning"

        risk_data[segment_id] = {
            "score": score,
            "status": status,
            "incidents": alert_count
        }

    return risk_data
