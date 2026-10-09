import html
import socket
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, TYPE_CHECKING

from app.config.settings import settings
from app.core.logging import logger

if TYPE_CHECKING:
    from app.schemas.booking_inquiry_schema import BookingInquiryDetailed
    from app.schemas.transport_schema import TransportBookingDetailResponse


def _escape_html(val: any) -> str:
    return html.escape(str(val)) if val is not None else ""


def _render_table(rows: list[tuple[str, any]], width_pct: str = "38%") -> str:
    parts = []
    for label, val in rows:
        display_val = _escape_html(val) if val is not None and str(val).strip() else "Not provided"
        parts.append(f"""
        <tr>
          <td style="padding:12px 16px;border:1px solid #e5dccb;background:#fbf7ef;color:#6b6257;font-family:Arial,sans-serif;font-size:13px;font-weight:600;vertical-align:top;width:{width_pct};">{_escape_html(label)}</td>
          <td style="padding:12px 16px;border:1px solid #e5dccb;background:#ffffff;color:#0a1628;font-family:Arial,sans-serif;font-size:14px;line-height:1.7;">{display_val}</td>
        </tr>""")
    return f"""<table style="width:100%;border-collapse:collapse;border-spacing:0;margin-bottom:20px;">{''.join(parts)}</table>"""


def _build_email_shell(overline: str, title: str, content_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f1e8;font-family:Arial,sans-serif;">
  <div style="background:#f5f1e8;padding:32px 16px;">
    <div style="max-width:760px;margin:0 auto;background:#ffffff;border:1px solid rgba(10,22,40,0.08);box-shadow:0 20px 50px rgba(10,22,40,0.08);">
      <div style="background:#0a1628;padding:28px 32px;">
        <p style="margin:0 0 10px;color:#c9a961;font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.35em;text-transform:uppercase;">{_escape_html(overline)}</p>
        <h1 style="margin:0;color:#ffffff;font-family:Georgia,serif;font-size:28px;font-weight:500;line-height:1.3;">{_escape_html(title)}</h1>
      </div>
      <div style="padding:32px;color:#0a1628;font-family:Arial,sans-serif;">
        {content_html}
      </div>
    </div>
  </div>
</body>
</html>"""


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

    def _send_message_smtp(self, msg) -> None:
        """
        Connects and delivers an email message via SMTP.
        Uses fast IPv4 connect with SNI and timeout to prevent 75s delays on macOS /
        local networks where IPv6 is unroutable.
        """
        try:
            addr_info = socket.getaddrinfo(self.smtp_host, self.smtp_port, socket.AF_INET, socket.SOCK_STREAM)
            if addr_info:
                ip_addr = addr_info[0][4][0]
                with smtplib.SMTP(timeout=8) as server:
                    server.connect(ip_addr, self.smtp_port)
                    server._host = self.smtp_host
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
                    return
        except Exception as fast_err:
            logger.debug("Fast IPv4 connect bypassed: %s", fast_err)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)

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
        """Send booking inquiry notification email to bookings@tourceylon.com / admin desk"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send booking inquiry notification")
            return False
            
        try:
            to_email = settings.INQUIRY_EMAIL or "bookings@tourceylon.com"
            admin_url = str(settings.ADMIN_APP_URL).rstrip("/")
            
            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"New Booking Inquiry - {inquiry.reference}"

            # Generate cart items summary
            cart_summary = ""
            cart_rows = []
            for item in inquiry.cart_items:
                if getattr(item, 'travel_date_end', None):
                    t_start = item.travel_date.strftime('%Y-%m-%d') if hasattr(item.travel_date, 'strftime') else str(item.travel_date)[:10]
                    t_end = item.travel_date_end.strftime('%Y-%m-%d') if hasattr(item.travel_date_end, 'strftime') else str(item.travel_date_end)[:10]
                    tdate_display = f"{t_start} to {t_end}"
                elif getattr(item, 'travel_date_raw', None) and " to " in str(item.travel_date_raw):
                    tdate_display = str(item.travel_date_raw)
                elif hasattr(item.travel_date, 'strftime'):
                    tdate_display = item.travel_date.strftime('%Y-%m-%d %H:%M')
                else:
                    tdate_display = str(item.travel_date)

                subtotal_str = f"{item.price * item.travel_count:.2f} {item.base_currency}"
                cart_summary += f"""
• {item.title}
  Travel Date: {tdate_display}
  Travelers: {item.travel_count}
  Price: {item.price} {item.base_currency}
  Subtotal: {subtotal_str}
"""
                cart_rows.append((item.title, f"Date: {tdate_display} | Travelers: {item.travel_count} | Total: {subtotal_str}"))

            plain_body = f"""Dear Team,

A new booking inquiry has been received:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INQUIRY REFERENCE: {inquiry.reference}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CUSTOMER INFORMATION:
  Name:              {inquiry.first_name} {inquiry.last_name}
  Email:             {inquiry.email}
  Phone:             {inquiry.phone}
  Nationality:       {inquiry.nationality}
  Emergency Contact: {inquiry.emergency_contact or 'Not provided'}

BOOKING DETAILS:
  Travelers:         {inquiry.number_of_travelers}
  Special Requests:  {inquiry.special_requests or 'None'}

REQUESTED ITEMS:{cart_summary}

PRICING SUMMARY:
  Subtotal:          {inquiry.subtotal} {inquiry.currency}
  Total:             {inquiry.total} {inquiry.currency}

Admin Portal: {admin_url}/inquiries

Warm regards,
Travel Ready Tours System
"""

            customer_rows = [
                ("Name", f"{inquiry.first_name} {inquiry.last_name}"),
                ("Email", inquiry.email),
                ("Phone", inquiry.phone),
                ("Nationality", inquiry.nationality),
                ("Emergency Contact", inquiry.emergency_contact or "Not provided"),
            ]

            inquiry_rows = [
                ("Inquiry Reference", inquiry.reference),
                ("Status", str(inquiry.status.value).upper()),
                ("Inquiry Date", inquiry.created_at.strftime('%B %d, %Y %I:%M %p')),
                ("Number of Travelers", str(inquiry.number_of_travelers)),
                ("Special Requests", inquiry.special_requests or "None specified"),
            ]

            pricing_rows = [
                ("Subtotal", f"{inquiry.subtotal} {inquiry.currency}"),
                ("Total Estimated", f"{inquiry.total} {inquiry.currency}"),
            ]

            content_html = f"""
              <p style="margin:0 0 20px;font-size:15px;line-height:1.8;">A new booking inquiry has been received from the website and is awaiting team review.</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Customer Information</h2>
              {_render_table(customer_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Inquiry Summary</h2>
              {_render_table(inquiry_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Requested Experiences / Items</h2>
              {_render_table(cart_rows, width_pct="45%")}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Pricing Summary</h2>
              {_render_table(pricing_rows)}

              <div style="margin:36px 0 16px;text-align:center;">
                <a href="{admin_url}/inquiries" style="display:inline-block;background:#0a1628;border:1px solid #c9a961;color:#ffffff;text-decoration:none;padding:14px 36px;font-family:Arial,sans-serif;font-size:13px;font-weight:600;letter-spacing:0.15em;text-transform:uppercase;">View in Admin Portal &rarr;</a>
              </div>

              <p style="margin:28px 0 0;font-size:13px;line-height:1.7;color:#6b6257;border-top:1px solid #e5dccb;padding-top:16px;">
                Travel Ready Tours Operations Desk<br />
                <a href="{admin_url}" style="color:#0a1628;font-weight:600;text-decoration:none;">Admin Portal</a>
              </p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours • Inquiry Desk",
                title=f"New Inquiry - {inquiry.reference}",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
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
            customer_full_name = f"{inquiry.first_name} {inquiry.last_name}".strip() or "Valued Traveler"
            
            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Thank you for your inquiry - Travel Ready Tours ({inquiry.reference})"

            cart_summary = ""
            cart_rows = []
            for item in inquiry.cart_items:
                if getattr(item, 'travel_date_end', None):
                    t_start = item.travel_date.strftime('%B %d, %Y') if hasattr(item.travel_date, 'strftime') else str(item.travel_date)[:10]
                    t_end = item.travel_date_end.strftime('%B %d, %Y') if hasattr(item.travel_date_end, 'strftime') else str(item.travel_date_end)[:10]
                    tdate_display = f"{t_start} to {t_end}"
                elif getattr(item, 'travel_date_raw', None) and " to " in str(item.travel_date_raw):
                    tdate_display = str(item.travel_date_raw)
                elif hasattr(item.travel_date, 'strftime'):
                    tdate_display = item.travel_date.strftime('%B %d, %Y at %I:%M %p')
                else:
                    tdate_display = str(item.travel_date)

                item_subtotal = f"{item.price * item.travel_count:.2f} {item.base_currency}"
                cart_summary += f"""
• {item.title}
  Travel Date: {tdate_display}
  Travelers: {item.travel_count}
  Price per person: {item.price} {item.base_currency}
  Subtotal: {item_subtotal}
"""
                cart_rows.append((item.title, f"Date: {tdate_display} | Travelers: {item.travel_count} | Subtotal: {item_subtotal}"))

            plain_body = f"""Dear {customer_full_name},

Thank you for reaching out to Travel Ready Tours.

We have received your inquiry for a customized Sri Lankan travel experience. Our travel team will carefully review your details and contact you soon to discuss your trip and help create a personalized itinerary that matches your interests, budget, and travel preferences.

Here are the details you submitted:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INQUIRY REFERENCE: {inquiry.reference}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR DETAILS:
  Name:              {customer_full_name}
  Email:             {inquiry.email}
  Contact Number:    {inquiry.phone}
  Country:           {inquiry.nationality}

TRAVEL PREFERENCES:
  Number of Travelers: {inquiry.number_of_travelers}
  Special Notes:       {inquiry.special_requests or 'None specified'}

REQUESTED EXPERIENCES:{cart_summary}

TOTAL ESTIMATED: {inquiry.total} {inquiry.currency}

One of our local destination experts will contact you shortly to understand your travel plans better and guide you through the next steps.

Thank you for choosing Travel Ready Tours. We look forward to helping you plan a memorable Sri Lankan adventure.

Warm regards,
Travel Ready Tours Team
www.trt.lk
"""

            customer_rows = [
                ("Name", customer_full_name),
                ("Email", inquiry.email),
                ("Contact Number", inquiry.phone),
                ("Country / Nationality", inquiry.nationality),
            ]

            preferences_rows = [
                ("Inquiry Reference", inquiry.reference),
                ("Number of Travelers", str(inquiry.number_of_travelers)),
                ("Additional Notes", inquiry.special_requests or "None specified"),
            ]

            pricing_rows = [
                ("Estimated Total", f"{inquiry.total} {inquiry.currency}"),
            ]

            content_html = f"""
              <p style="margin:0 0 20px;font-size:16px;line-height:1.8;">Dear {_escape_html(customer_full_name)},</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.9;">Thank you for reaching out to Travel Ready Tours.</p>
              <p style="margin:0 0 24px;font-size:15px;line-height:1.9;">We have received your inquiry for a customized Sri Lankan travel experience. Our travel team will carefully review your details and contact you soon to discuss your trip and help create a personalized itinerary that matches your interests, budget, and travel preferences.</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.9;">Here are the details you submitted:</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Your Details</h2>
              {_render_table(customer_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Travel Preferences</h2>
              {_render_table(preferences_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Requested Itinerary &amp; Items</h2>
              {_render_table(cart_rows, width_pct="45%")}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Pricing Summary</h2>
              {_render_table(pricing_rows)}

              <div style="margin:24px 0;padding:20px;border:1px solid #e5dccb;background:#fbf7ef;">
                <p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#0a1628;">What to Expect Next:</p>
                <p style="margin:0;font-size:14px;line-height:1.8;color:#6b6257;">One of our local destination experts will contact you shortly via email or WhatsApp/phone to refine your travel plans and provide personalized recommendations.</p>
              </div>

              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">Thank you for choosing Travel Ready Tours. We look forward to helping you plan a memorable Sri Lankan adventure.</p>
              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">Warm regards,<br />Travel Ready Tours Team<br /><a href="http://www.trt.lk" style="color:#0a1628;">www.trt.lk</a></p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours",
                title="Thank you for your inquiry",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
            logger.info("Customer confirmation email sent for %s to %s", inquiry.reference, to_email)
            return True
            
        except Exception as e:
            logger.error("Failed to send customer confirmation email for %s: %s", inquiry.reference, str(e))
            return False

    def send_vendor_booking_accepted_email(self, inquiry: 'BookingInquiryDetailed') -> bool:
        """Send vendor booking confirmation email to customer when vendor accepts booking"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - logging vendor booking acceptance email for %s", inquiry.reference)
            return False

        try:
            to_email = inquiry.email
            if not to_email:
                return False

            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"🎉 Booking Confirmed! - REF: {inquiry.reference}"

            cart_summary = ""
            for item in inquiry.cart_items:
                if getattr(item, 'travel_date_end', None):
                    t_start = item.travel_date.strftime('%B %d, %Y') if hasattr(item.travel_date, 'strftime') else str(item.travel_date)[:10]
                    t_end = item.travel_date_end.strftime('%B %d, %Y') if hasattr(item.travel_date_end, 'strftime') else str(item.travel_date_end)[:10]
                    tdate = f"{t_start} to {t_end}"
                elif getattr(item, 'travel_date_raw', None) and " to " in str(item.travel_date_raw):
                    tdate = str(item.travel_date_raw)
                elif hasattr(item.travel_date, 'strftime'):
                    tdate = item.travel_date.strftime('%B %d, %Y')
                else:
                    tdate = str(item.travel_date)

                cart_summary += f"""
• {item.title}
  Travel Date: {tdate}
  Travelers: {item.travel_count}
  Price per person: {item.price} {item.base_currency}
  Subtotal: {item.price * item.travel_count} {item.base_currency}
"""

            body = f"""
Dear {inquiry.first_name} {inquiry.last_name},

Great news! Your booking request with Tour Ceylon has been APPROVED & CONFIRMED by the vendor!

CONFIRMED BOOKING DETAILS:
Reference Number: {inquiry.reference}
Guest Name: {inquiry.first_name} {inquiry.last_name}
Email: {inquiry.email}
Phone: {inquiry.phone}

ITEMS & ROOM RESERVATIONS:{cart_summary}

TOTAL AMOUNT: {inquiry.total} {inquiry.currency}
SPECIAL REQUESTS / NOTES: {inquiry.special_requests or 'None'}

RESERVATION STATUS:
Your room unit allocation is officially confirmed and locked in the property calendar under Reference #{inquiry.reference}.

Thank you for booking with Tour Ceylon! We look forward to hosting you.

Best regards,
Tour Ceylon Team
Email: {self.email_from}
"""
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("Vendor booking acceptance email sent to %s for ref %s", to_email, inquiry.reference)
            return True
        except Exception as e:
            logger.error("Failed to send vendor booking acceptance email for %s: %s", inquiry.reference, str(e))
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

    # =========================================================================
    # TRANSPORT BOOKING EMAILS
    # =========================================================================

    def send_transport_booking_notification(self, booking: 'TransportBookingDetailResponse') -> bool:
        """Send transport booking notification email to admin/business team"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send transport booking notification")
            return False

        try:
            to_email = settings.INQUIRY_EMAIL or "bookings@tourceylon.com"
            admin_url = str(settings.ADMIN_APP_URL).rstrip("/")

            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"🚗 New Transport Booking - {booking.booking_reference}"

            # Vehicle category name (if available)
            vehicle_name = booking.vehicle_category.name if booking.vehicle_category else "N/A"
            vehicle_passengers = booking.vehicle_category.passenger_capacity if booking.vehicle_category else "N/A"
            vehicle_luggage = booking.vehicle_category.luggage_capacity if booking.vehicle_category else "N/A"

            # Format travel date & pickup time
            travel_date_str = booking.travel_date.strftime('%B %d, %Y') if hasattr(booking.travel_date, 'strftime') else str(booking.travel_date)
            pickup_time_str = booking.pickup_time.strftime('%I:%M %p') if hasattr(booking.pickup_time, 'strftime') else str(booking.pickup_time)

            # ---- Plain text version ----
            plain_body = f"""Dear Team,

A new TRANSPORT BOOKING has been received and requires attention.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOOKING REFERENCE: {booking.booking_reference}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRIP OVERVIEW:
  Pickup:        {booking.pickup_location}
  Destination:   {booking.destination_location}
  Distance:      {booking.distance_km} km
  Est. Duration: {booking.estimated_duration_minutes} minutes
  Travel Date:   {travel_date_str}
  Pickup Time:   {pickup_time_str}

CUSTOMER CONTACT:
  Name:    {booking.customer_name}
  Email:   {booking.customer_email}
  Phone:   {booking.customer_phone}
  Country: {booking.customer_country or 'Not provided'}

VEHICLE & REQUIREMENTS:
  Category:   {vehicle_name}
  Passengers: {booking.passengers_count} (Vehicle capacity: {vehicle_passengers})
  Luggage:    {booking.luggage_count} (Vehicle capacity: {vehicle_luggage})
  Special Requests: {booking.special_requests or 'None'}

PRICING:
  Base Fare:     {booking.base_fare} {booking.currency}
  Route Price:   {booking.route_price} {booking.currency}
  Extra Charges: {booking.extra_charges} {booking.currency}
  TOTAL:         {booking.total_price} {booking.currency}
  Payment:       {booking.payment_status.upper()}

ACTION REQUIRED:
  Please assign a driver and confirm this booking promptly.
  Admin Portal: {admin_url}/transport/requests

Best regards,
Tour Ceylon System
"""

            # ---- HTML version ----
            itinerary_rows = [
                ("Booking Reference", booking.booking_reference),
                ("Pickup Location", booking.pickup_location),
                ("Destination", booking.destination_location),
                ("Travel Date", travel_date_str),
                ("Pickup Time", pickup_time_str),
                ("Estimated Distance", f"{booking.distance_km} km"),
                ("Estimated Duration", f"{booking.estimated_duration_minutes} minutes"),
            ]

            customer_rows = [
                ("Customer Name", booking.customer_name),
                ("Email Address", booking.customer_email),
                ("Contact Number", booking.customer_phone),
                ("Country", booking.customer_country or "Not provided"),
            ]

            vehicle_rows = [
                ("Vehicle Category", vehicle_name),
                ("Passengers", f"{booking.passengers_count} (Max capacity: {vehicle_passengers})"),
                ("Luggage Count", f"{booking.luggage_count} bags (Max capacity: {vehicle_luggage})"),
                ("Special Requests", booking.special_requests or "None"),
            ]

            pricing_rows = [
                ("Base Fare", f"{booking.base_fare} {booking.currency}"),
                ("Route Price", f"{booking.route_price} {booking.currency}"),
                ("Extra Charges", f"{booking.extra_charges} {booking.currency}"),
                ("Total Fare", f"{booking.total_price} {booking.currency}"),
                ("Payment Status", booking.payment_status.upper()),
            ]

            content_html = f"""
              <p style="margin:0 0 20px;font-size:15px;line-height:1.8;">A new transport booking has been received and requires driver dispatch.</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Trip Itinerary</h2>
              {_render_table(itinerary_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Customer Details</h2>
              {_render_table(customer_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Vehicle &amp; Requirements</h2>
              {_render_table(vehicle_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Pricing &amp; Payment</h2>
              {_render_table(pricing_rows)}

              <div style="margin:36px 0 16px;text-align:center;">
                <a href="{admin_url}/transport/requests" style="display:inline-block;background:#0a1628;border:1px solid #c9a961;color:#ffffff;text-decoration:none;padding:14px 36px;font-family:Arial,sans-serif;font-size:13px;font-weight:600;letter-spacing:0.15em;text-transform:uppercase;">View &amp; Assign Driver &rarr;</a>
              </div>

              <p style="margin:28px 0 0;font-size:13px;line-height:1.7;color:#6b6257;border-top:1px solid #e5dccb;padding-top:16px;">
                Travel Ready Tours Operations Desk &bull; Automated Dispatch<br />
                <a href="{admin_url}" style="color:#0a1628;font-weight:600;text-decoration:none;">Admin Dispatch Console</a>
              </p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours • Dispatch Desk",
                title=f"New Transport Booking - {booking.booking_reference}",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
            logger.info("Transport booking notification sent for %s", booking.booking_reference)
            return True

        except Exception as e:
            logger.error("Failed to send transport booking notification for %s: %s", booking.booking_reference, str(e))
            return False

    def send_transport_booking_customer_confirmation(self, booking: 'TransportBookingDetailResponse') -> bool:
        """Send transport booking confirmation email to customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send transport customer confirmation email")
            return False

        try:
            to_email = booking.customer_email

            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"Transport Booking Confirmed - REF: {booking.booking_reference}"

            # Vehicle category name (if available)
            vehicle_name = booking.vehicle_category.name if booking.vehicle_category else "Private Vehicle"
            vehicle_passengers = booking.vehicle_category.passenger_capacity if booking.vehicle_category else "N/A"
            vehicle_luggage = booking.vehicle_category.luggage_capacity if booking.vehicle_category else "N/A"

            # Format travel date & pickup time
            travel_date_str = booking.travel_date.strftime('%B %d, %Y') if hasattr(booking.travel_date, 'strftime') else str(booking.travel_date)
            pickup_time_str = booking.pickup_time.strftime('%I:%M %p') if hasattr(booking.pickup_time, 'strftime') else str(booking.pickup_time)

            # ---- Plain text version ----
            plain_body = f"""Dear {booking.customer_name},

Thank you for booking your private transfer with Tour Ceylon! Your booking has been received and is being processed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOOKING REFERENCE: {booking.booking_reference}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR TRANSFER DETAILS:
  Pickup:      {booking.pickup_location}
  Destination: {booking.destination_location}
  Distance:    {booking.distance_km} km (approx. {booking.estimated_duration_minutes} mins)
  Travel Date: {travel_date_str}
  Pickup Time: {pickup_time_str}

VEHICLE INFORMATION:
  Category:    {vehicle_name}
  Passengers:  {booking.passengers_count} (Max capacity: {vehicle_passengers})
  Luggage:     {booking.luggage_count} (Max capacity: {vehicle_luggage})

PRICING SUMMARY:
  Total Price: {booking.total_price} {booking.currency}
  Payment:     {booking.payment_status.upper()}

SPECIAL REQUESTS: {booking.special_requests or 'None'}

WHAT HAPPENS NEXT:
1. Our operations team will review your booking and assign a verified driver.
2. You will receive a confirmation with your driver's details (name, vehicle, and contact) before your travel date.
3. Your driver will arrive at the pickup location at the scheduled time.

IMPORTANT INFORMATION:
• Please be ready at the pickup location 5 minutes before the scheduled time.
• Your driver will display a Tour Ceylon sign for easy identification.
• Free waiting time: 30 minutes at airports, 15 minutes at other locations.
• For any route changes on the day, please coordinate directly with your driver.

NEED HELP?
If you have any questions or need to modify your booking, please contact us:
  Email: {self.email_from}
  Phone: +94 (0) 123-456-789
  Reference: {booking.booking_reference}

We look forward to providing you with a comfortable journey across Sri Lanka!

Best regards,
Tour Ceylon Team

---
This is an automated confirmation email. Please do not reply directly to this message.
If you need immediate assistance, please contact us using the details above.
"""

            # ---- HTML version ----
            itinerary_rows = [
                ("Booking Reference", booking.booking_reference),
                ("Pickup Location", booking.pickup_location),
                ("Destination", booking.destination_location),
                ("Travel Date", travel_date_str),
                ("Pickup Time", pickup_time_str),
                ("Estimated Duration", f"{booking.estimated_duration_minutes} minutes"),
                ("Distance", f"{booking.distance_km} km"),
            ]

            vehicle_rows = [
                ("Vehicle Category", vehicle_name),
                ("Travelers", f"{booking.passengers_count} (Max: {vehicle_passengers})"),
                ("Luggage Count", f"{booking.luggage_count} bags (Max: {vehicle_luggage})"),
                ("Special Requests", booking.special_requests or "None specified"),
            ]

            pricing_rows = [
                ("Total Fare", f"{booking.total_price} {booking.currency}"),
                ("Payment Status", booking.payment_status.upper()),
            ]

            content_html = f"""
              <p style="margin:0 0 18px;font-size:16px;line-height:1.8;">Dear {_escape_html(booking.customer_name)},</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.9;">Thank you for choosing Travel Ready Tours for your private transfer across Sri Lanka. We have received your booking details and our operations team is currently arranging a verified driver for your journey.</p>
              <p style="margin:0 0 22px;font-size:15px;line-height:1.9;">Here are the confirmed details of your booking request:</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Trip Itinerary</h2>
              {_render_table(itinerary_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Vehicle &amp; Passenger Details</h2>
              {_render_table(vehicle_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Pricing Summary</h2>
              {_render_table(pricing_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Next Steps</h2>
              <div style="margin:0 0 24px;padding:24px;border:1px solid #e5dccb;background:#fbf7ef;">
                <p style="margin:0 0 12px;font-size:14px;font-weight:600;color:#0a1628;">What Happens Next:</p>
                <ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.8;color:#6b6257;">
                  <li style="margin-bottom:6px;">Our operations team will review your route and assign a certified, professional driver.</li>
                  <li style="margin-bottom:6px;">You will receive an email update with your driver's direct phone number, name, and vehicle registration number.</li>
                  <li>Your driver will meet you at the pickup location displaying a personalized welcome sign.</li>
                </ol>
              </div>

              <div style="margin:20px 0;padding:16px 20px;border-left:3px solid #c9a961;background:#faf6ed;font-size:14px;line-height:1.7;color:#6b6257;">
                <strong style="color:#0a1628;">Meeting Instructions:</strong> Free waiting time is 30 minutes for airport arrivals and 15 minutes for hotel lobbies. Please ensure you are ready at the pickup point 5 minutes before scheduled pickup.
              </div>

              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">One of our local destination experts or your driver will coordinate with you prior to departure.</p>
              <p style="margin:18px 0 0;font-size:15px;line-height:1.9;">Thank you for choosing Travel Ready Tours. We look forward to providing you with a comfortable, memorable journey across Sri Lanka.</p>
              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">Warm regards,<br />Travel Ready Tours Team<br /><a href="http://www.trt.lk" style="color:#0a1628;">www.trt.lk</a></p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours",
                title="Thank you for your transfer booking",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
            logger.info("Transport customer confirmation email sent for %s to %s", booking.booking_reference, to_email)
            return True

        except Exception as e:
            logger.error("Failed to send transport customer confirmation for %s: %s", booking.booking_reference, str(e))
            return False

    def send_transport_driver_assignment_notification(self, booking: any, driver: any) -> bool:
        """Send trip assignment notification email to the assigned driver"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send driver assignment email")
            return False

        try:
            # Extract driver user and email
            driver_user = getattr(driver, "user", None)
            driver_email = getattr(driver_user, "email", None) if driver_user else getattr(driver, "email", None)
            driver_name = getattr(driver_user, "full_name", "Valued Driver") if driver_user else getattr(driver, "full_name", "Valued Driver")
            
            if not driver_email:
                logger.warning("Driver has no email configured - cannot send assignment notification")
                return False

            ref = getattr(booking, "booking_reference", "N/A")
            customer_name = getattr(booking, "customer_name", "Customer")
            customer_phone = getattr(booking, "customer_phone", "N/A")
            pickup_location = getattr(booking, "pickup_location", "N/A")
            destination_location = getattr(booking, "destination_location", "N/A")
            distance_km = getattr(booking, "distance_km", "0")
            duration_min = getattr(booking, "estimated_duration_minutes", "0")
            passengers_count = getattr(booking, "passengers_count", 1)
            luggage_count = getattr(booking, "luggage_count", 0)
            special_requests = getattr(booking, "special_requests", None) or "None"

            travel_date = getattr(booking, "travel_date", None)
            travel_date_str = travel_date.strftime('%B %d, %Y') if hasattr(travel_date, 'strftime') else str(travel_date)
            pickup_time = getattr(booking, "pickup_time", None)
            pickup_time_str = pickup_time.strftime('%I:%M %p') if hasattr(pickup_time, 'strftime') else str(pickup_time)

            vehicle_make = getattr(driver, "vehicle_make", "")
            vehicle_model = getattr(driver, "vehicle_model", "")
            vehicle_plate = getattr(driver, "vehicle_plate_number", "")
            vehicle_str = f"{vehicle_make} {vehicle_model} ({vehicle_plate})".strip()

            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = driver_email
            msg['Subject'] = f"🚗 New Trip Assigned: {ref} - {pickup_location} → {destination_location}"

            plain_body = f"""Dear {driver_name},

You have been assigned to a new transport trip with Tour Ceylon!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIP REFERENCE: {ref}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCHEDULE & ROUTE:
  Travel Date:       {travel_date_str}
  Pickup Time:       {pickup_time_str}
  Pickup Location:   {pickup_location}
  Destination:       {destination_location}
  Est. Distance:     {distance_km} km (approx. {duration_min} mins)

PASSENGER DETAILS:
  Passenger Name:    {customer_name}
  Contact Phone:     {customer_phone}
  Passengers:        {passengers_count}
  Luggage Count:     {luggage_count}
  Special Requests:  {special_requests}

ASSIGNED VEHICLE:
  Vehicle:           {vehicle_str}

DRIVER INSTRUCTIONS:
1. Please arrive at the pickup location at least 10 minutes prior to scheduled time.
2. Hold a Travel Ready Tours sign with the passenger's name ({customer_name}) at the arrival area.
3. Ensure the vehicle is clean, air conditioning is operational, and complimentary drinking water is ready.
4. If you encounter traffic delays, notify dispatch and the passenger immediately.

For operational support or dispatch queries, contact Travel Ready Tours Operations:
Email: {self.email_from} | Phone: +94 (0) 123-456-789

Best regards,
Travel Ready Tours Dispatch Team
"""

            # ---- HTML version ----
            schedule_rows = [
                ("Trip Reference", ref),
                ("Travel Date", travel_date_str),
                ("Pickup Time", pickup_time_str),
                ("Pickup Location", pickup_location),
                ("Destination", destination_location),
                ("Estimated Distance", f"{distance_km} km"),
                ("Estimated Duration", f"{duration_min} minutes"),
            ]

            passenger_rows = [
                ("Passenger Name", customer_name),
                ("Contact Phone", customer_phone),
                ("Travelers", f"{passengers_count} passenger(s)"),
                ("Luggage Count", f"{luggage_count} bag(s)"),
                ("Special Requests", special_requests),
            ]

            vehicle_rows = [
                ("Assigned Vehicle", vehicle_str),
                ("Plate Number", vehicle_plate or "Registered Vehicle"),
            ]

            content_html = f"""
              <p style="margin:0 0 18px;font-size:16px;line-height:1.8;">Dear {_escape_html(driver_name)},</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.9;">You have been assigned to a new private transfer with Travel Ready Tours. Please review your trip itinerary, passenger details, and dispatch schedule below.</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Trip Schedule</h2>
              {_render_table(schedule_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Passenger Details</h2>
              {_render_table(passenger_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Vehicle Information</h2>
              {_render_table(vehicle_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Driver Guidelines</h2>
              <div style="margin:0 0 24px;padding:24px;border:1px solid #e5dccb;background:#fbf7ef;">
                <p style="margin:0 0 12px;font-size:14px;font-weight:600;color:#0a1628;">Service Standards:</p>
                <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.8;color:#6b6257;">
                  <li style="margin-bottom:6px;">Arrive at the pickup point at least 10 minutes prior to scheduled pickup time.</li>
                  <li style="margin-bottom:6px;">Display a Travel Ready Tours welcome sign with the passenger's name (<strong>{_escape_html(customer_name)}</strong>).</li>
                  <li style="margin-bottom:6px;">Assist the passenger with luggage handling.</li>
                  <li>Ensure the vehicle is clean, climate-controlled, and drinking water is prepared.</li>
                </ul>
              </div>

              <p style="margin:24px 0 0;font-size:14px;line-height:1.8;color:#6b6257;border-top:1px solid #e5dccb;padding-top:16px;">
                Travel Ready Tours Operations Desk &bull; Driver Dispatch<br />
                Hotline: +94 (0) 123-456-789 &bull; Email: {self.email_from}
              </p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours • Driver Dispatch",
                title=f"New Trip Assignment - {ref}",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
            logger.info("Driver assignment notification sent to %s for %s", driver_email, ref)
            return True

        except Exception as e:
            logger.error("Failed to send driver assignment notification for %s: %s", getattr(booking, "booking_reference", "unknown"), str(e))
            return False

    def send_transport_driver_assigned_customer_email(self, booking: any, driver: any) -> bool:
        """Send driver assignment & vehicle info email to the customer"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured - cannot send customer driver assigned email")
            return False

        try:
            to_email = getattr(booking, "customer_email", None)
            if not to_email:
                logger.warning("Customer has no email - cannot send driver assigned email")
                return False

            ref = getattr(booking, "booking_reference", "N/A")
            customer_name = getattr(booking, "customer_name", "Valued Customer")
            pickup_location = getattr(booking, "pickup_location", "N/A")
            destination_location = getattr(booking, "destination_location", "N/A")
            distance_km = getattr(booking, "distance_km", "0")
            duration_min = getattr(booking, "estimated_duration_minutes", "0")

            travel_date = getattr(booking, "travel_date", None)
            travel_date_str = travel_date.strftime('%B %d, %Y') if hasattr(travel_date, 'strftime') else str(travel_date)
            pickup_time = getattr(booking, "pickup_time", None)
            pickup_time_str = pickup_time.strftime('%I:%M %p') if hasattr(pickup_time, 'strftime') else str(pickup_time)

            driver_user = getattr(driver, "user", None)
            driver_name = getattr(driver_user, "full_name", "Travel Ready Tours Driver") if driver_user else getattr(driver, "full_name", "Travel Ready Tours Driver")
            driver_phone = "N/A"
            if driver_user and getattr(driver_user, "business_profile", None):
                driver_phone = driver_user.business_profile.get("phone", "N/A")
            elif hasattr(driver, "phone") and driver.phone:
                driver_phone = driver.phone

            vehicle_make = getattr(driver, "vehicle_make", "")
            vehicle_model = getattr(driver, "vehicle_model", "")
            vehicle_plate = getattr(driver, "vehicle_plate_number", "")
            vehicle_str = f"{vehicle_make} {vehicle_model}".strip() or "Standard Transfer Vehicle"
            
            rating_val = getattr(driver, "rating", None)
            rating_str = f"{float(rating_val):.1f} ★" if rating_val else "5.0 ★ Verified"

            msg = MIMEMultipart("alternative")
            msg['From'] = self.email_from
            msg['To'] = to_email
            msg['Subject'] = f"🚗 Your Driver Has Been Assigned! - REF: {ref}"

            plain_body = f"""Dear {customer_name},

Great news! A dedicated professional driver has been assigned to your private transfer with Travel Ready Tours.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOOKING REFERENCE: {ref}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR ASSIGNED DRIVER & VEHICLE:
  Driver Name:       {driver_name}
  Contact Phone:     {driver_phone}
  Driver Rating:     {rating_str}
  Vehicle:           {vehicle_str}
  License Plate:     {vehicle_plate}

TRIP ITINERARY:
  Pickup Location:   {pickup_location}
  Destination:       {destination_location}
  Travel Date:       {travel_date_str}
  Pickup Time:       {pickup_time_str}
  Est. Distance:     {distance_km} km ({duration_min} mins)

MEETING YOUR DRIVER:
• Airport Arrivals: Your driver will wait at the arrival hall holding a Travel Ready Tours welcome sign with your name ({customer_name}).
• Free Waiting Time: 30 minutes for airport pickups, 15 minutes for hotel and other locations.
• On Travel Day: Feel free to call or WhatsApp your driver directly at {driver_phone}.

Warm regards,
Travel Ready Tours Team
www.trt.lk
"""

            # ---- HTML version ----
            driver_rows = [
                ("Driver Name", driver_name),
                ("Contact Phone", driver_phone),
                ("Driver Rating", rating_str),
                ("Vehicle Details", vehicle_str),
                ("License Plate", vehicle_plate or "Registered Commercial Vehicle"),
            ]

            itinerary_rows = [
                ("Booking Reference", ref),
                ("Pickup Location", pickup_location),
                ("Destination", destination_location),
                ("Travel Date", travel_date_str),
                ("Pickup Time", pickup_time_str),
                ("Estimated Duration", f"{duration_min} minutes"),
                ("Estimated Distance", f"{distance_km} km"),
            ]

            content_html = f"""
              <p style="margin:0 0 18px;font-size:16px;line-height:1.8;">Dear {_escape_html(customer_name)},</p>
              <p style="margin:0 0 18px;font-size:15px;line-height:1.9;">Great news! A dedicated professional driver has been assigned to your upcoming transfer with Travel Ready Tours. You can find your driver's contact details, vehicle information, and trip schedule below.</p>

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Assigned Driver &amp; Vehicle</h2>
              {_render_table(driver_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Trip Itinerary</h2>
              {_render_table(itinerary_rows)}

              <h2 style="margin:28px 0 12px;font-family:Georgia,serif;font-size:22px;font-weight:500;color:#0a1628;">Meeting Your Driver</h2>
              <div style="margin:0 0 24px;padding:24px;border:1px solid #e5dccb;background:#fbf7ef;">
                <ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.8;color:#6b6257;">
                  <li style="margin-bottom:8px;"><strong>Signboard Greeting:</strong> Your driver will be waiting at the pickup point holding a personalized Travel Ready Tours signboard with your name (<strong>{_escape_html(customer_name)}</strong>).</li>
                  <li style="margin-bottom:8px;"><strong>Complimentary Waiting Time:</strong> 30 minutes for airport arrival pickups and 15 minutes for hotel/city pickups.</li>
                  <li><strong>Direct Coordination:</strong> You may contact your driver directly at <strong>{_escape_html(driver_phone)}</strong> if your plans change or if you need assistance locating them.</li>
                </ul>
              </div>

              <div style="margin:20px 0;padding:16px 20px;border-left:3px solid #c9a961;background:#faf6ed;font-size:14px;line-height:1.7;color:#6b6257;">
                <strong style="color:#0a1628;">Need Support?</strong> Our operations team is available around the clock. If you have any questions or require modifications, please contact our dispatch desk at <a href="mailto:{self.email_from}" style="color:#0a1628;font-weight:600;">{self.email_from}</a>.
              </div>

              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">Thank you for choosing Travel Ready Tours. We look forward to delivering a seamless and comfortable journey across Sri Lanka.</p>
              <p style="margin:24px 0 0;font-size:15px;line-height:1.9;">Warm regards,<br />Travel Ready Tours Team<br /><a href="http://www.trt.lk" style="color:#0a1628;">www.trt.lk</a></p>
            """

            html_body = _build_email_shell(
                overline="Travel Ready Tours • Driver Assigned",
                title="Your Driver Has Been Assigned",
                content_html=content_html
            )

            msg.attach(MIMEText(plain_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            self._send_message_smtp(msg)
            logger.info("Customer driver assigned email sent for %s to %s", ref, to_email)
            return True

        except Exception as e:
            logger.error("Failed to send customer driver assigned email for %s: %s", getattr(booking, "booking_reference", "unknown"), str(e))
            return False


email_provider = EmailProvider()
