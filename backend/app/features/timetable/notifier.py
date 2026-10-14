"""Notification helper for timetable processing events."""
import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class NotificationManager:
    """Sends notifications for timetable processing events.
    
    Supports Slack webhook and email notifications.
    Configure via environment variables:
    - SLACK_WEBHOOK_URL: Slack incoming webhook URL
    - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD: Email settings
    """
    
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM", "noreply@campuspilot.local")
        self.email_to = os.getenv("EMAIL_TO", "").split(",") if os.getenv("EMAIL_TO") else []
    
    async def send_slack(self, message: str, attachments: Optional[List[Dict]] = None) -> bool:
        """Send a Slack message via webhook."""
        if not self.slack_webhook:
            logger.debug("No Slack webhook configured, skipping")
            return False
        
        payload = {"text": message}
        if attachments:
            payload["attachments"] = attachments
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.slack_webhook, json=payload)
                if response.status_code == 200:
                    logger.info("Slack notification sent")
                    return True
                else:
                    logger.warning(f"Slack notification failed: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False
    
    async def send_email(self, subject: str, body: str) -> bool:
        """Send an email notification."""
        if not all([self.smtp_host, self.smtp_user, self.smtp_password, self.email_to]):
            logger.debug("Email not configured, skipping")
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg["From"] = self.email_from
            msg["To"] = ", ".join(self.email_to)
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info("Email notification sent")
            return True
        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False
    
    async def notify_success(
        self,
        slots_count: int,
        version: str,
        excel_path: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ):
        """Send success notification."""
        message = f"Timetable processed successfully: {slots_count} slots (Version {version})"
        
        if warnings:
            message += f"\nWarnings: {len(warnings)}"
        
        await self.send_slack(message)
        
        # Also send email with details
        body = f"""
Timetable Processing Complete
============================
Version: {version}
Slots parsed: {slots_count}
Timestamp: {datetime.now().isoformat()}
Excel: {excel_path or 'N/A'}
Warnings: {warnings or 'None'}
        """.strip()
        
        await self.send_email(
            subject=f"[CampusPilot] Timetable v{version} processed",
            body=body,
        )
    
    async def notify_failure(self, error: str, pdf_path: Optional[str] = None):
        """Send failure notification."""
        message = f"Timetable processing FAILED: {error}"
        
        await self.send_slack(message)
        
        body = f"""
Timetable Processing Failed
==========================
Error: {error}
PDF: {pdf_path or 'N/A'}
Timestamp: {datetime.now().isoformat()}
        """.strip()
        
        await self.send_email(
            subject="[CampusPilot] Timetable processing FAILED",
            body=body,
        )


# Global instance
_notification_manager: Optional[NotificationManager] = None


def get_notifier() -> NotificationManager:
    """Get or create global notification manager."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager