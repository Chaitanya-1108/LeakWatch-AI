from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class WaterQualitySimulationMode(str, Enum):
    NORMAL = "normal"
    CHEMICAL_CONTAMINATION = "chemical_contamination"
    DIRTY_WATER = "dirty_water"
    INDUSTRIAL_POLLUTION = "industrial_pollution"


class WaterCondition(str, Enum):
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    CONTAMINATED = "CONTAMINATED"
    DANGEROUS = "DANGEROUS"


class WaterQualityReading(BaseModel):
    timestamp: datetime
    pipeline_id: str
    ph: float = Field(..., description="Potential of hydrogen (pH scale)")
    turbidity: float = Field(..., description="Turbidity in NTU")
    tds: float = Field(..., description="Total dissolved solids in ppm")
    temperature: float = Field(..., description="Water temperature in Celsius")
    dissolved_oxygen: float = Field(..., description="Dissolved oxygen in mg/L")
    mode: WaterQualitySimulationMode


class WaterQualityAssessmentInput(BaseModel):
    ph: float
    turbidity: float
    tds: float
    temperature: float
    dissolved_oxygen: float


class WaterQualityAssessment(BaseModel):
    timestamp: datetime
    condition: WaterCondition
    risk_score: float
    reasons: list[str]
    reading: WaterQualityAssessmentInput


class WaterQualityState(BaseModel):
    is_active: bool
    current_mode: WaterQualitySimulationMode


class WQIQualityCategory(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    POOR = "Poor"
    UNSAFE = "Unsafe"


class WQIResult(BaseModel):
    wqi_score: float
    quality_category: WQIQualityCategory


class WaterQualityRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WaterQualityPredictionResponse(BaseModel):
    timestamp: datetime
    pipeline_id: str | None = None
    sensor_values: WaterQualityAssessmentInput
    ai_prediction: WaterCondition
    wqi_score: float
    risk_level: WaterQualityRiskLevel


class WaterQualityPredictRequest(BaseModel):
    pipeline_id: str | None = None
    ph: float
    turbidity: float
    tds: float
    temperature: float
    dissolved_oxygen: float
