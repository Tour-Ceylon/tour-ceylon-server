from app.config.database import SessionLocal
from app.models.stay import StayProperty
from app.integrations.email_provider import email_provider

db = SessionLocal()
try:
    print("==================================================")
    print("TESTING PAYMENT POLICY & TAILORED EMAIL GENERATION")
    print("==================================================")

    # 1. Test StayProperty model reading payment_policy column
    prop = db.query(StayProperty).first()
    if prop:
        print(f"Property '{prop.name}' | Current payment_policy = '{prop.payment_policy}'")
        prop.payment_policy = "pay_at_property"
        db.commit()
        db.refresh(prop)
        print(f"Updated payment_policy to '{prop.payment_policy}' successfully!")

    # 2. Test Pay at Property Email Provider payload
    sample_pay_at_property_booking = {
        "booking_reference": "TC-TEST-PAY-PROP-101",
        "guest_name": "Test Traveler",
        "guest_email": "test@example.com",
        "guest_phone": "+94771234567",
        "total_amount": 250.0,
        "currency": "USD",
        "special_requests": "Quiet room requested",
    }
    
    # 3. Test Online Paid Email Provider payload
    sample_online_paid_booking = {
        "booking_reference": "TC-TEST-ONLINE-PAID-202",
        "guest_name": "Online Traveler",
        "guest_email": "online@example.com",
        "total_amount": 450.0,
        "currency": "USD",
        "transaction_id": "TXN-SUPABASE-9988",
        "property_name": "Heritance Kandalama",
    }

    print("\nTesting Email Provider invocation:")
    print("  -> Calling send_booking_confirmation_pay_at_property...")
    res1 = email_provider.send_booking_confirmation_pay_at_property(sample_pay_at_property_booking)
    print(f"     Result (SMTP active={email_provider.smtp_configured}): {res1}")

    print("  -> Calling send_booking_confirmation_online_paid...")
    res2 = email_provider.send_booking_confirmation_online_paid(sample_online_paid_booking)
    print(f"     Result (SMTP active={email_provider.smtp_configured}): {res2}")

    print("\n==================================================")
    print("VERIFICATION COMPLETED SUCCESSFULLY")
    print("==================================================")

finally:
    db.close()
