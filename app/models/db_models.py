from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.session import Base

class LeakAlert(Base):
    __tablename__ = "leak_alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    is_leak = Column(Boolean, default=False)
    confidence = Column(Float)
    severity_score = Column(Float)
    severity = Column(String)  # "Minor", "Moderate", "Critical"
    location = Column(String, nullable=True)
    analysis = Column(String, nullable=True)
    
    # Store feature highlights for quick reference
    avg_pressure = Column(Float)
    avg_flow = Column(Float)
    acoustic_peak = Column(Float)

class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    pressure = Column(Float)
    flow_rate = Column(Float)
    acoustic_signal = Column(Float)
    mode = Column(String) # Simulation mode at time of reading

class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("leak_alerts.id"))
    status = Column(String, default="Pending") # Pending, In Progress, Resolved
    assigned_technician = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    alert = relationship("LeakAlert")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="operator") # operator, admin, supervisor
    is_active = Column(Boolean, default=True)


class LeakImagePrediction(Base):
    __tablename__ = "leak_image_predictions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    filename = Column(String, nullable=False)
    leak_type = Column(String, nullable=False)
    severity_level = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    recommended_solution = Column(String, nullable=False)
    detections_json = Column(Text, nullable=False)


class WaterQualityReadingRecord(Base):
    __tablename__ = "water_quality_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    pipeline_id = Column(String, index=True, nullable=False)
    ph = Column(Float, nullable=False)
    turbidity = Column(Float, nullable=False)
    tds = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    dissolved_oxygen = Column(Float, nullable=False)
    mode = Column(String, nullable=False)
