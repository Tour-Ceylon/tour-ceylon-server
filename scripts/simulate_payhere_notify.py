"""Send a signed PayHere notification to a running local server.

Usage (from tour-ceylon-server, with the same .env the server uses):
    python scripts/simulate_payhere_notify.py ORDER_ID AMOUNT CURRENCY [STATUS_CODE]
    python scripts/simulate_payhere_notify.py TRT-TR-20261101-AB12-1a2b3c4d 100.00 USD 2

STATUS_CODE: 2 success (default), 0 pending, -1 cancelled, -2 failed, -3 chargedback.
Equivalent curl (compute md5sig as in docs/PAYMENTS.md):
    curl -X POST http://localhost:8000/api/v1/payments/payhere/notify \
      -d merchant_id=... -d order_id=... -d payment_id=320032 \
      -d payhere_amount=100.00 -d payhere_currency=USD -d status_code=2 -d md5sig=...
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")  # config import only; no DB is opened

from app.config.settings import settings  # noqa: E402
from app.payments.providers.payhere import PayHereProvider  # noqa: E402


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    order_id, amount, currency = sys.argv[1:4]
    code = sys.argv[4] if len(sys.argv) > 4 else "2"
    base = os.environ.get("SERVER_URL", "http://localhost:8000").rstrip("/")

    provider = PayHereProvider(
        settings.PAYHERE_MERCHANT_ID, settings.PAYHERE_MERCHANT_SECRET, settings.PAYHERE_MODE
    )
    body = urlencode(
        {
            "merchant_id": settings.PAYHERE_MERCHANT_ID,
            "order_id": order_id,
            "payment_id": "SIM-" + order_id[-8:],
            "payhere_amount": amount,
            "payhere_currency": currency,
            "status_code": code,
            "md5sig": provider.notification_signature(order_id, amount, currency, code),
        }
    ).encode()
    req = Request(
        f"{base}{settings.API_V1_PREFIX}/payments/payhere/notify",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(req, timeout=15) as res:
            print(res.status, res.read().decode())
    except HTTPError as exc:
        print(exc.code, exc.read().decode())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
