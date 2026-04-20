import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config.settings import settings
from app.core.logging import logger


class EmailProvider:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.email_from = settings.EMAIL_FROM
        
        # Check if SMTP is configured
        self.smtp_configured = all([self.smtp_host, self.smtp_user, self.smtp_password, self.email_from])
        
        if not self.smtp_configured:
            logger.warning("SMTP configuration incomplete - email functionality will be disabled")

    def send_otp_email(self, to_email: str, otp_code: str, app_name: str = "Tour Ceylon") -> bool:
        """Send OTP email to user"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Your {app_name} verification code"

            body = f"""Dear user,

Your verification code is: **{otp_code}**

This code expires in 10 minutes. Do not share it with anyone.

If you didn't request this, please ignore this email.

Best,
{app_name} Team
"""

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info("OTP email sent to %s", to_email)
            return True
            
        except Exception as e:
            logger.error("Failed to send OTP to %s: %s", to_email, str(e))
            return False


email_provider = EmailProvider()