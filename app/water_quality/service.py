import random
from datetime import datetime
from pathlib import Path
import joblib
import pandas as pd
from .models import (
    WaterCondition,
    WaterQualityAssessment,
    WaterQualityAssessmentInput,
    WaterQualityPredictionResponse,
    WaterQualityRiskLevel,
    WaterQualityReading,
    WaterQualitySimulationMode,
    WQIQualityCategory,
    WQIResult,
)


class WaterQualityService:
    def __init__(self):
        self.mode = WaterQualitySimulationMode.NORMAL
        self._model_artifact = None
        self._model_path = Path("app/water_quality/artifacts/water_quality_rf.joblib")
        self.turbidity_high_threshold = 5.0
        self.tds_abnormal_threshold = 500.0
        self.pipeline_ids = [
            "PL-001",
            "PL-002",
            "PL-003",
            "PL-004",
            "PL-005",
        ]

    def set_mode(self, mode: WaterQualitySimulationMode):
        self.mode = mode

    def generate_next_reading(self) -> WaterQualityReading:
        mode_ranges = {
            WaterQualitySimulationMode.NORMAL: {
                "ph": (6.8, 8.0),
                "turbidity": (0.5, 4.0),
                "tds": (80.0, 280.0),
                "temperature": (18.0, 28.0),
                "dissolved_oxygen": (6.0, 9.0),
            },
            WaterQualitySimulationMode.CHEMICAL_CONTAMINATION: {
                "ph": (5.2, 10.8),
                "turbidity": (4.0, 25.0),
                "tds": (350.0, 1300.0),
                "temperature": (20.0, 36.0),
                "dissolved_oxygen": (2.5, 6.0),
            },
            WaterQualitySimulationMode.DIRTY_WATER: {
                "ph": (6.0, 8.8),
                "turbidity": (15.0, 130.0),
                "tds": (300.0, 1200.0),
                "temperature": (19.0, 34.0),
                "dissolved_oxygen": (1.0, 5.0),
            },
            WaterQualitySimulationMode.INDUSTRIAL_POLLUTION: {
                "ph": (4.5, 11.5),
                "turbidity": (25.0, 180.0),
                "tds": (800.0, 2600.0),
                "temperature": (24.0, 45.0),
                "dissolved_oxygen": (0.5, 4.0),
            },
        }
        ranges = mode_ranges[self.mode]

        return WaterQualityReading(
            timestamp=datetime.now(),
            pipeline_id=random.choice(self.pipeline_ids),
            ph=round(random.uniform(*ranges["ph"]), 2),
            turbidity=round(random.uniform(*ranges["turbidity"]), 2),
            tds=round(random.uniform(*ranges["tds"]), 2),
            temperature=round(random.uniform(*ranges["temperature"]), 2),
            dissolved_oxygen=round(random.uniform(*ranges["dissolved_oxygen"]), 2),
            mode=self.mode,
        )

    @staticmethod
    def _band_for_ph(value: float) -> tuple[int, str]:
        if 6.5 <= value <= 8.5:
            return 0, "pH is in acceptable range"
        if 6.0 <= value < 6.5 or 8.5 < value <= 9.0:
            return 1, "pH is slightly outside ideal range"
        if 5.0 <= value < 6.0 or 9.0 < value <= 10.0:
            return 2, "pH indicates contamination risk"
        return 3, "pH is at a dangerous level"

    @staticmethod
    def _band_for_turbidity(value: float) -> tuple[int, str]:
        if value <= 5:
            return 0, "Turbidity is low"
        if value <= 15:
            return 1, "Turbidity is elevated"
        if value <= 50:
            return 2, "Turbidity indicates contamination"
        return 3, "Turbidity is critically high"

    @staticmethod
    def _band_for_tds(value: float) -> tuple[int, str]:
        if value <= 300:
            return 0, "TDS is in safe range"
        if value <= 600:
            return 1, "TDS is above preferred range"
        if value <= 1200:
            return 2, "TDS indicates contamination"
        return 3, "TDS is at a dangerous level"

    @staticmethod
    def _band_for_temperature(value: float) -> tuple[int, str]:
        if 10 <= value <= 30:
            return 0, "Temperature is in normal range"
        if 8 <= value < 10 or 30 < value <= 35:
            return 1, "Temperature is mildly abnormal"
        if 5 <= value < 8 or 35 < value <= 40:
            return 2, "Temperature may stress water quality"
        return 3, "Temperature is critically abnormal"

    @staticmethod
    def _band_for_do(value: float) -> tuple[int, str]:
        if value >= 6:
            return 0, "Dissolved oxygen is healthy"
        if value >= 4:
            return 1, "Dissolved oxygen is below ideal"
        if value >= 2:
            return 2, "Dissolved oxygen indicates contamination risk"
        return 3, "Dissolved oxygen is dangerously low"

    def assess(self, payload: WaterQualityAssessmentInput) -> WaterQualityAssessment:
        checks = [
            self._band_for_ph(payload.ph),
            self._band_for_turbidity(payload.turbidity),
            self._band_for_tds(payload.tds),
            self._band_for_temperature(payload.temperature),
            self._band_for_do(payload.dissolved_oxygen),
        ]
        scores = [score for score, _ in checks]
        max_score = max(scores)
        mean_score = sum(scores) / len(scores)
        risk_score = round((0.65 * max_score + 0.35 * mean_score) * 100 / 3, 2)

        if max_score >= 3 or risk_score >= 75:
            condition = WaterCondition.DANGEROUS
        elif max_score >= 2 or risk_score >= 50:
            condition = WaterCondition.CONTAMINATED
        elif max_score >= 1 or risk_score >= 25:
            condition = WaterCondition.MODERATE
        else:
            condition = WaterCondition.SAFE

        reasons = [reason for score, reason in checks if score > 0]
        if not reasons:
            reasons = ["All monitored water parameters are within safe limits"]

        return WaterQualityAssessment(
            timestamp=datetime.now(),
            condition=condition,
            risk_score=risk_score,
            reasons=reasons,
            reading=payload,
        )

    @staticmethod
    def _ph_wqi_score(value: float) -> float:
        if 6.5 <= value <= 8.5:
            return 100.0
        if 6.0 <= value < 6.5 or 8.5 < value <= 9.0:
            return 85.0
        if 5.0 <= value < 6.0 or 9.0 < value <= 10.0:
            return 60.0
        return 25.0

    @staticmethod
    def _turbidity_wqi_score(value: float) -> float:
        if value <= 5:
            return 100.0
        if value <= 15:
            return 80.0
        if value <= 50:
            return 55.0
        return 25.0

    @staticmethod
    def _tds_wqi_score(value: float) -> float:
        if value <= 300:
            return 100.0
        if value <= 600:
            return 80.0
        if value <= 1200:
            return 55.0
        return 20.0

    @staticmethod
    def _temperature_wqi_score(value: float) -> float:
        if 15 <= value <= 30:
            return 100.0
        if 10 <= value < 15 or 30 < value <= 35:
            return 80.0
        if 5 <= value < 10 or 35 < value <= 40:
            return 55.0
        return 25.0

    @staticmethod
    def _do_wqi_score(value: float) -> float:
        if value >= 6:
            return 100.0
        if value >= 4:
            return 80.0
        if value >= 2:
            return 55.0
        return 20.0

    def calculate_wqi(self, payload: WaterQualityAssessmentInput) -> WQIResult:
        weighted_score = (
            0.2 * self._ph_wqi_score(payload.ph)
            + 0.2 * self._turbidity_wqi_score(payload.turbidity)
            + 0.2 * self._tds_wqi_score(payload.tds)
            + 0.2 * self._temperature_wqi_score(payload.temperature)
            + 0.2 * self._do_wqi_score(payload.dissolved_oxygen)
        )
        wqi_score = round(max(0.0, min(100.0, weighted_score)), 2)

        if wqi_score >= 90:
            category = WQIQualityCategory.EXCELLENT
        elif wqi_score >= 70:
            category = WQIQualityCategory.GOOD
        elif wqi_score >= 50:
            category = WQIQualityCategory.POOR
        else:
            category = WQIQualityCategory.UNSAFE

        return WQIResult(
            wqi_score=wqi_score,
            quality_category=category,
        )

    def _load_model_artifact(self):
        if self._model_artifact is not None:
            return self._model_artifact
        if self._model_path.exists():
            self._model_artifact = joblib.load(self._model_path)
        return self._model_artifact

    def _predict_from_model(self, payload: WaterQualityAssessmentInput) -> tuple[WaterCondition, float]:
        artifact = self._load_model_artifact()
        if not artifact:
            raise FileNotFoundError("Water quality model artifact not found")

        model = artifact["model"]
        features = artifact.get(
            "features",
            ["ph", "turbidity", "tds", "temperature", "dissolved_oxygen"],
        )

        input_df = pd.DataFrame(
            [
                {
                    "ph": payload.ph,
                    "turbidity": payload.turbidity,
                    "tds": payload.tds,
                    "temperature": payload.temperature,
                    "dissolved_oxygen": payload.dissolved_oxygen,
                }
            ]
        )
        predicted = str(model.predict(input_df[features])[0]).upper()
        if predicted not in WaterCondition.__members__:
            predicted = "MODERATE"

        confidence = 0.0
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(input_df[features])[0]
            confidence = float(max(probabilities))

        return WaterCondition[predicted], round(confidence, 4)

    @staticmethod
    def _risk_from_prediction(prediction: WaterCondition) -> WaterQualityRiskLevel:
        mapping = {
            WaterCondition.SAFE: WaterQualityRiskLevel.LOW,
            WaterCondition.MODERATE: WaterQualityRiskLevel.MEDIUM,
            WaterCondition.CONTAMINATED: WaterQualityRiskLevel.HIGH,
            WaterCondition.DANGEROUS: WaterQualityRiskLevel.CRITICAL,
        }
        return mapping[prediction]

    def predict_quality(
        self,
        payload: WaterQualityAssessmentInput,
        pipeline_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> WaterQualityPredictionResponse:
        try:
            ai_prediction, _ = self._predict_from_model(payload)
        except Exception:
            ai_prediction = self.assess(payload).condition

        wqi = self.calculate_wqi(payload)
        risk_level = self._risk_from_prediction(ai_prediction)
        return WaterQualityPredictionResponse(
            timestamp=timestamp or datetime.now(),
            pipeline_id=pipeline_id,
            sensor_values=payload,
            ai_prediction=ai_prediction,
            wqi_score=wqi.wqi_score,
            risk_level=risk_level,
        )

    def evaluate_alert_conditions(
        self, prediction: WaterQualityPredictionResponse
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        values = prediction.sensor_values

        if values.ph < 6.0 or values.ph > 8.5:
            reasons.append(f"pH out of range ({values.ph})")

        if values.turbidity > self.turbidity_high_threshold:
            reasons.append(
                f"Turbidity high ({values.turbidity} NTU > {self.turbidity_high_threshold} NTU)"
            )

        if values.tds > self.tds_abnormal_threshold:
            reasons.append(
                f"TDS abnormal ({values.tds} ppm > {self.tds_abnormal_threshold} ppm)"
            )

        if prediction.ai_prediction in {
            WaterCondition.CONTAMINATED,
            WaterCondition.DANGEROUS,
        }:
            reasons.append(
                f"AI predicted {prediction.ai_prediction.value}"
            )

        return len(reasons) > 0, reasons

    def build_dashboard_alert(
        self,
        prediction: WaterQualityPredictionResponse,
        reasons: list[str],
    ) -> dict:
        is_critical = prediction.ai_prediction == WaterCondition.DANGEROUS
        severity = "Critical" if is_critical else "Warning"
        severity_score = round(max(0.0, min(100.0, 100.0 - prediction.wqi_score)), 2)
        analysis = (
            " | ".join(reasons)
            if reasons
            else "Water quality anomaly detected."
        )

        return {
            "event": "WATER_QUALITY_ALERT",
            "severity": severity,
            "severity_score": severity_score,
            "location": prediction.pipeline_id or "Unknown",
            "analysis": analysis,
            "timestamp": prediction.timestamp.isoformat(),
            "ai_prediction": prediction.ai_prediction.value,
            "wqi_score": prediction.wqi_score,
            "risk_level": prediction.risk_level.value,
            "sensor_values": prediction.sensor_values.model_dump(),
        }


water_quality_service = WaterQualityService()
