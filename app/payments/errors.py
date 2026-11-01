class PaymentError(Exception):
    """A payment request the caller can fix or must abandon; carries an HTTP status."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
