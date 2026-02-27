from datetime import datetime
from sqlalchemy.orm import Session

from app.chatbot.models import ChatMessageResponse
from app.models.db_models import LeakAlert, LeakImagePrediction, WaterQualityReadingRecord
from app.simulation.service import simulator_engine
from app.water_quality.models import WaterQualityAssessmentInput
from app.water_quality.service import water_quality_service


class OpsChatbotService:
    @staticmethod
    def _water_snapshot(db: Session) -> tuple[str, str]:
        latest = (
            db.query(WaterQualityReadingRecord)
            .order_by(WaterQualityReadingRecord.timestamp.desc())
            .first()
        )
        if not latest:
            return "No water-quality records yet.", "Try enabling contaminated mode to test alerts."

        payload = WaterQualityAssessmentInput(
            ph=latest.ph,
            turbidity=latest.turbidity,
            tds=latest.tds,
            temperature=latest.temperature,
            dissolved_oxygen=latest.dissolved_oxygen,
        )
        prediction = water_quality_service.predict_quality(
            payload=payload,
            pipeline_id=latest.pipeline_id,
            timestamp=latest.timestamp,
        )
        safe = prediction.ai_prediction.value == "SAFE" and prediction.wqi_score >= 70
        status = "safe to drink" if safe else "NOT safe to drink"
        summary = (
            f"Water status for {prediction.pipeline_id}: {prediction.ai_prediction.value}, "
            f"WQI={prediction.wqi_score}, risk={prediction.risk_level.value}. "
            f"Current decision: {status}."
        )
        hint = "Use 'chemical_contamination' or 'industrial_pollution' mode to simulate alerts."
        return summary, hint

    @staticmethod
    def _leak_snapshot(db: Session) -> str:
        latest = (
            db.query(LeakAlert)
            .order_by(LeakAlert.timestamp.desc())
            .first()
        )
        if not latest:
            return f"No leak alerts recorded recently. Simulation mode is '{simulator_engine.mode.value}'."
        return (
            f"Latest leak alert: severity={latest.severity}, score={latest.severity_score}, "
            f"location={latest.location}, time={latest.timestamp}."
        )

    @staticmethod
    def _image_snapshot(db: Session) -> str:
        latest = (
            db.query(LeakImagePrediction)
            .order_by(LeakImagePrediction.timestamp.desc())
            .first()
        )
        if not latest:
            return "No image-detection history yet. Upload an infrastructure image to start."
        return (
            f"Latest image result: {latest.leak_type} ({latest.severity_level}) "
            f"with confidence {round(latest.confidence_score * 100, 2)}%."
        )

    def respond(self, message: str, db: Session) -> ChatMessageResponse:
        text = (message or "").strip().lower()
        suggestions = [
            "Show overall health",
            "Is water safe to drink?",
            "Latest leak alert",
            "Latest image detection",
        ]

        if not text:
            answer = (
                "I’m here. Ask me anything about water safety, leak activity, image detections, "
                "or overall system health."
            )
        elif any(k in text for k in ["water", "drink", "wqi", "contamin"]):
            summary, hint = self._water_snapshot(db)
            answer = (
                f"Here’s what I’m seeing right now: {summary} "
                f"If you want, I can also walk you through which sensor values are driving this. {hint}"
            )
        elif any(k in text for k in ["leak", "pressure", "burst"]):
            answer = (
                f"I checked the leak pipeline for you. {self._leak_snapshot(db)} "
                "If you want, I can suggest the next operator action."
            )
        elif any(k in text for k in ["image", "photo", "camera", "upload"]):
            answer = (
                f"I just looked at the latest image analysis. {self._image_snapshot(db)} "
                "You can upload another image anytime and I’ll compare trends."
            )
        elif any(k in text for k in ["overall", "health", "status", "system"]):
            leak = self._leak_snapshot(db)
            image = self._image_snapshot(db)
            water, _ = self._water_snapshot(db)
            answer = (
                "Here’s a quick plain-language summary. "
                f"{water} "
                f"{leak} "
                f"{image} "
                "Overall, the platform is responding normally in simulation mode."
            )
        else:
            answer = (
                "Got it. I can help with water safety, leak alerts, image detection, and overall health. "
                "Try asking: 'Is the water safe to drink right now?'"
            )

        return ChatMessageResponse(timestamp=datetime.now(), answer=answer, suggestions=suggestions)


ops_chatbot_service = OpsChatbotService()
