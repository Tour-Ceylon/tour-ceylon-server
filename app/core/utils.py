import random
import string

def generate_otp(length: int = 6) -> str:
    """Generate random 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=length))

def generate_secure_token(length: int = 32) -> str:
    """Generate secure random token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
