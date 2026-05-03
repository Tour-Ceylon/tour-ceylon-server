import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, TYPE_CHECKING

from app.config.settings import settings
from app.core.logging import logger

if TYPE_CHECKING:
    from app.schemas.booking_inquiry_schema import BookingInquiryDetailed


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

    def send_booking_inquiry_notification(self, inquiry: 'BookingInquiryDetailed') -> bool:
        """Send booking inquiry notification email to bookings@tourceylon.com"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send booking inquiry notification")
            return False
            
        try:
            to_email = settings.INQUIRY_EMAIL or "bookings@tourceylon.com"
            
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"New Booking Inquiry - {inquiry.reference}"

            # Generate cart items summary
            cart_summary = ""
            for item in inquiry.cart_items:
                cart_summary += f"""
• {item.title}
  Travel Date: {item.travel_date.strftime('%Y-%m-%d %H:%M')}
  Travelers: {item.travel_count}
  Price: {item.price} {item.base_currency}
  Subtotal: {item.price * item.travel_count} {item.base_currency}
"""

            # Create email body
            body = f"""
Dear Team,

A new booking inquiry has been received:

INQUIRY DETAILS:
Reference: {inquiry.reference}
Status: {inquiry.status.value}
Created: {inquiry.created_at.strftime('%Y-%m-%d %H:%M:%S')}

CUSTOMER INFORMATION:
Name: {inquiry.first_name} {inquiry.last_name}
Email: {inquiry.email}
Phone: {inquiry.phone}
Nationality: {inquiry.nationality}
Emergency Contact: {inquiry.emergency_contact or 'Not provided'}

BOOKING DETAILS:
Number of Travelers: {inquiry.number_of_travelers}
Special Requests: {inquiry.special_requests or 'None'}

CART ITEMS:{cart_summary}

PRICING SUMMARY:
Subtotal: {inquiry.subtotal} {inquiry.currency}
Total: {inquiry.total} {inquiry.currency}

Please contact the customer to follow up on this inquiry.

Best regards,
Tour Ceylon System
"""

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info("Booking inquiry notification sent for %s", inquiry.reference)
            return True
            
        except Exception as e:
            logger.error("Failed to send booking inquiry notification for %s: %s", inquiry.reference, str(e))
            return False

    def send_booking_inquiry_customer_confirmation(self, inquiry: 'BookingInquiryDetailed') -> bool:
        """Send booking inquiry confirmation email to customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send customer confirmation email")
            return False
            
        try:
            to_email = inquiry.email
            
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Booking Inquiry Confirmed - REF: {inquiry.reference}"

            # Generate cart items summary for customer
            cart_summary = ""
            total_amount = 0
            for item in inquiry.cart_items:
                item_total = item.price * item.travel_count
                total_amount += item_total
                cart_summary += f"""
• {item.title}
  Travel Date: {item.travel_date.strftime('%B %d, %Y at %I:%M %p')}
  Travelers: {item.travel_count}
  Price per person: {item.price} {item.base_currency}
  Subtotal: {item_total} {item.base_currency}
"""

            # Create customer-friendly email body
            body = f"""
Dear {inquiry.first_name} {inquiry.last_name},

Thank you for your booking inquiry with Tour Ceylon! We have successfully received your request and our team is excited to help plan your perfect Sri Lankan adventure.

INQUIRY DETAILS:
Reference Number: {inquiry.reference}
Inquiry Date: {inquiry.created_at.strftime('%B %d, %Y at %I:%M %p')}
Status: Under Review

YOUR BOOKING REQUEST:{cart_summary}

TOTAL AMOUNT: {inquiry.total} {inquiry.currency}
NUMBER OF TRAVELERS: {inquiry.number_of_travelers}

SPECIAL REQUESTS: {inquiry.special_requests or 'None specified'}

NEXT STEPS:
Our experienced travel consultants will review your inquiry and contact you within 24 hours to discuss your travel plans in detail. We will reach out to you at:

Phone: {inquiry.phone}
Email: {inquiry.email}

In the meantime, if you have any questions or would like to make changes to your inquiry, please don't hesitate to contact us using your reference number: {inquiry.reference}

We look forward to creating unforgettable memories for your Sri Lankan journey!

Best regards,
Tour Ceylon Team
Email: {self.email_from}
Phone: +94 (0) 123-456-789

---
This is an automated confirmation email. Please do not reply directly to this message.
If you need immediate assistance, please contact us using the details above.
"""

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info("Customer confirmation email sent for %s to %s", inquiry.reference, to_email)
            return True
            
        except Exception as e:
            logger.error("Failed to send customer confirmation email for %s: %s", inquiry.reference, str(e))
            return False


email_provider = EmailProvider()
