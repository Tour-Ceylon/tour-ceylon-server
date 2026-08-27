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

    def send_booking_confirmation_pay_at_property(self, booking_data: dict) -> bool:
        """Send Pay at Property booking confirmation email to customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging Pay at Property booking confirmation email for %s", booking_data.get("booking_reference"))
            return False
            
        try:
            to_email = booking_data.get("guest_email") or booking_data.get("email")
            if not to_email:
                return False
                
            ref = booking_data.get("booking_reference", "TC-BKG")
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Booking Confirmed - Ref: {ref} (Pay at Property)"

            body = f"""Dear {booking_data.get('guest_name', 'Valued Customer')},

Thank you for booking with Tour Ceylon! Your reservation has been CONFIRMED.

BOOKING DETAILS:
Reference Number: {ref}
Booking Status: CONFIRMED
Payment Method: Pay at Property (Cash/Card at Check-in)
Total Amount Due at Property: {booking_data.get('total_amount')} {booking_data.get('currency', 'USD')}

GUEST INFORMATION:
Name: {booking_data.get('guest_name')}
Email: {to_email}
Phone: {booking_data.get('guest_phone', 'N/A')}
Special Requests: {booking_data.get('special_requests', 'None')}

CANCELLATION POLICY:
Free cancellation up to 48 hours before check-in. Please present your booking reference upon arrival.

We look forward to hosting you!

Best regards,
Tour Ceylon Team
"""
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Pay at property confirmation email sent to %s for %s", to_email, ref)
            return True
        except Exception as e:
            logger.error("Failed to send Pay at Property email for %s: %s", booking_data.get("booking_reference"), str(e))
            return False

    def send_booking_confirmation_online_paid(self, booking_data: dict) -> bool:
        """Send Full Online Prepayment booking confirmation & digital receipt email to customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging Online Paid confirmation email for %s", booking_data.get("booking_reference"))
            return False
            
        try:
            to_email = booking_data.get("guest_email") or booking_data.get("email")
            if not to_email:
                return False
                
            ref = booking_data.get("booking_reference", "TC-BKG")
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Booking Confirmed & Payment Received - Ref: {ref}"

            body = f"""Dear {booking_data.get('guest_name', 'Valued Customer')},

Thank you for booking with Tour Ceylon! Your payment has been RECEIVED and your reservation is FULLY CONFIRMED.

PAYMENT & RECEIPT SUMMARY:
Reference Number: {ref}
Booking Status: CONFIRMED
Payment Status: PAID ONLINE (100% Prepayment Received)
Total Paid: {booking_data.get('total_amount')} {booking_data.get('currency', 'USD')}
Transaction Reference: {booking_data.get('transaction_id', 'ONLINE-PAY-DIRECT')}

RESERVATION DETAILS:
Property / Listing: {booking_data.get('property_name', booking_data.get('listing_name', 'Tour Ceylon Listing'))}
Guest Name: {booking_data.get('guest_name')}
Email: {to_email}
Special Requests: {booking_data.get('special_requests', 'None')}

IMPORTANT CHECK-IN INSTRUCTIONS:
No payment is required at the property upon arrival. Please present your booking reference ({ref}) and a valid photo ID during check-in.

We look forward to hosting you!

Best regards,
Tour Ceylon Team
"""
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Online paid confirmation email sent to %s for %s", to_email, ref)
            return True
        except Exception as e:
            logger.error("Failed to send Online Paid confirmation email for %s: %s", booking_data.get("booking_reference"), str(e))
            return False

    def send_booking_bank_transfer_instructions(self, booking_data: dict) -> bool:
        """Send Bank Transfer instructions email to customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging Bank Transfer instructions email for %s", booking_data.get("booking_reference"))
            return False
            
        try:
            to_email = booking_data.get("guest_email") or booking_data.get("email")
            if not to_email:
                return False
                
            ref = booking_data.get("booking_reference", "TC-BKG")
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Reservation Reserved - Bank Transfer Required (Ref: {ref})"

            body = f"""Dear {booking_data.get('guest_name', 'Valued Customer')},

Your reservation has been HELD. Please complete your bank transfer within 24-48 hours to confirm your booking.

BOOKING DETAILS:
Reference Number: {ref}
Booking Status: PENDING (Awaiting Payment)
Total Amount: {booking_data.get('total_amount')} {booking_data.get('currency', 'USD')}

BANK TRANSFER DETAILS:
Bank Name: Bank of Ceylon / Commercial Bank
Account Name: Tour Ceylon Holdings Pvt Ltd
Account Number: 1000-8899-2233
Swift Code: BCEYLKLX
Payment Reference / Description: MUST INCLUDE {ref}

NEXT STEPS:
Once you complete the bank transfer, please upload your receipt reference on the Tour Ceylon portal or reply to this email with your receipt.

Best regards,
Tour Ceylon Team
"""
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Bank transfer instructions email sent to %s for %s", to_email, ref)
            return True
        except Exception as e:
            logger.error("Failed to send Bank Transfer instructions email for %s: %s", booking_data.get("booking_reference"), str(e))
            return False

    def send_vendor_new_booking_alert(self, booking_data: dict, vendor_email: str = None) -> bool:
        """Send new booking alert to vendor and admin team"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging vendor alert for %s", booking_data.get("booking_reference"))
            return False
        try:
            to_email = vendor_email or settings.INQUIRY_EMAIL or "bookings@tourceylon.com"
            ref = booking_data.get("booking_reference", "TC-BKG")
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"New Booking Received - Ref: {ref}"

            body = f"""Dear Partner / Business Team,

A new booking has been placed on Tour Ceylon:

BOOKING REF: {ref}
Payment Method: {booking_data.get('payment_method')}
Status: {booking_data.get('status')}
Customer: {booking_data.get('guest_name')} ({booking_data.get('guest_email')})
Total Amount: {booking_data.get('total_amount')} {booking_data.get('currency', 'USD')}

Please log in to your Vendor Portal to view complete details.

Best regards,
Tour Ceylon System
"""
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Vendor alert email sent to %s for %s", to_email, ref)
            return True
        except Exception as e:
            logger.error("Failed to send vendor alert email for %s: %s", booking_data.get("booking_reference"), str(e))
            return False

    def send_vendor_receipt_submission_alert(self, booking_data: dict, receipt_ref: str, vendor_email: str = None) -> bool:
        """Send receipt submission alert to vendor and admin team"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging receipt submission alert for %s", booking_data.get("booking_reference"))
            return False
        try:
            to_email = vendor_email or settings.INQUIRY_EMAIL or "bookings@tourceylon.com"
            ref = booking_data.get("booking_reference", "TC-BKG")
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"ACTION REQUIRED: Payment Receipt Uploaded - Ref: {ref}"

            body = f"""Dear Partner / Business Team,

A customer has uploaded a bank transfer payment receipt for booking {ref}:

Receipt Reference / Details: {receipt_ref}
Customer Name: {booking_data.get('guest_name')} ({booking_data.get('guest_email')})
Amount Due: {booking_data.get('total_amount')} {booking_data.get('currency', 'USD')}

Please log in to your Vendor Portal and review the receipt, then click 'Mark as Paid' to confirm the booking.

Best regards,
Tour Ceylon System
"""
            msg.attach(MIMEText(body, 'plain'))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info("Receipt submission alert sent to %s for %s", to_email, ref)
            return True
        except Exception as e:
            logger.error("Failed to send receipt submission alert for %s: %s", booking_data.get("booking_reference"), str(e))
            return False


email_provider = EmailProvider()
