import logging
import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

# Configure logging for notifications
logger = logging.getLogger("leak_notifications")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class NotificationManager:
    def __init__(self):
        self.notification_enabled = True
        self.max_leak_email_sends = int(os.getenv("LEAK_EMAIL_MAX_SENDS", "5"))
        self._leak_email_send_count = 0
        self.alert_email = os.getenv("ALERT_EMAIL", "")
        self.alert_phone = os.getenv("ALERT_PHONE", "+1234567890")

        # SMTP settings
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from = os.getenv("SMTP_FROM") or self.smtp_user or "alerts@leakwatch.ai"

    def _resolve_sender(self) -> str:
        """
        Gmail SMTP often rejects arbitrary FROM values.
        If using Gmail SMTP, prefer SMTP_USER as sender.
        """
        sender = self.smtp_from
        if self.smtp_server and "gmail" in self.smtp_server.lower() and self.smtp_user:
            if sender.lower() != self.smtp_user.lower():
                logger.warning(
                    "SMTP_FROM (%s) differs from SMTP_USER (%s). Using SMTP_USER as sender.",
                    sender,
                    self.smtp_user,
                )
                return self.smtp_user
        return sender

    def send_leak_alert(self, severity: str, location: str, analysis: str):
        """Send leak alert via simulated SMS and SMTP email."""
        if not self.notification_enabled:
            return

        message = (
            f"URGENT: {severity} Leak Detected!\n"
            f"Location: {location}\n"
            f"Analysis: {analysis}\n"
            f"Action: Immediate inspection required."
        )
        self._simulate_sms(message)
        if self._leak_email_send_count < self.max_leak_email_sends:
            self._send_email(message, subject="LeakWatch AI Leak Alert")
            self._leak_email_send_count += 1
        else:
            logger.warning(
                "Leak email send limit reached (%s). Skipping leak email notification.",
                self.max_leak_email_sends,
            )

    def send_water_quality_alert(
        self,
        severity: str,
        pipeline_id: str,
        ai_prediction: str,
        wqi_score: float,
        analysis: str,
    ):
        """Send water-quality alert via simulated SMS and SMTP email."""
        if not self.notification_enabled:
            return

        message = (
            f"Water Quality Alert [{severity}]\n"
            f"Pipeline: {pipeline_id}\n"
            f"AI Prediction: {ai_prediction}\n"
            f"WQI Score: {wqi_score}\n"
            f"Details: {analysis}"
        )
        self._simulate_sms(message)
        self._send_email(message, subject="LeakWatch AI Water Quality Alert")

    def send_issue_resolved_alert(
        self,
        ticket_id: int,
        location: str,
        notes: str | None = None,
    ):
        if not self.notification_enabled:
            return

        message = (
            f"Issue Resolved\n"
            f"Maintenance Ticket: #{ticket_id}\n"
            f"Location: {location}\n"
            f"Notes: {notes or 'No additional notes'}\n"
            f"Status: Resolved"
        )
        self._simulate_sms(message)
        self._send_email(message, subject="LeakWatch AI Issue Resolved")

    def _simulate_sms(self, message: str):
        logger.info("[SMS SIMULATION] -> %s", self.alert_phone)
        logger.info("Message: %s", message)

    def _send_email(self, message: str, subject: str):
        if not all([self.smtp_server, self.smtp_user, self.smtp_password, self.alert_email]):
            logger.info("[EMAIL SIMULATION] -> %s", self.alert_email or "<missing ALERT_EMAIL>")
            logger.info("Message: %s", message)
            logger.warning(
                "For real emails set ALERT_EMAIL, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD (and optionally SMTP_FROM)."
            )
            return

        try:
            msg = MIMEText(message, _charset="utf-8")
            msg["Subject"] = subject
            msg["From"] = self._resolve_sender()
            msg["To"] = self.alert_email

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("[REAL EMAIL SENT] -> %s", self.alert_email)
        except Exception as exc:
            logger.error("Failed to send real email: %s", exc)


notification_manager = NotificationManager()
