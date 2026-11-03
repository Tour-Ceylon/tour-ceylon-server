from app.config.settings import settings

SUPPORTED_PROVIDERS = ("payhere",)


def validate_payment_config() -> None:
    """Fail fast at startup when the selected provider is not fully configured.

    An empty PAYMENT_PROVIDER leaves online payments disabled.
    """
    provider = (settings.PAYMENT_PROVIDER or "").strip().lower()
    if not provider:
        return

    if provider not in SUPPORTED_PROVIDERS:
        raise RuntimeError(
            f"Unsupported PAYMENT_PROVIDER '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    # The emailed payment links are signed with SECRET_KEY, so the shipped default is unsafe in production.
    if settings.ENV == "production" and settings.SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
        raise RuntimeError("Set SECRET_KEY to a long random value before running with online payments in production")

    if provider == "payhere":
        missing = [
            name
            for name in ("PAYHERE_MERCHANT_ID", "PAYHERE_MERCHANT_SECRET")
            if not getattr(settings, name)
        ]
        if missing:
            raise RuntimeError(f"PAYMENT_PROVIDER=payhere requires {', '.join(missing)}")
        if settings.PAYHERE_MODE not in ("sandbox", "live"):
            raise RuntimeError("PAYHERE_MODE must be 'sandbox' or 'live'")


def get_provider():
    """Return the configured provider adapter. Add new providers here."""
    from app.payments.base import PaymentProviderError

    provider = (settings.PAYMENT_PROVIDER or "").strip().lower()
    if not provider:
        raise PaymentProviderError("Online payments are not enabled")

    if provider == "payhere":
        from app.payments.providers.payhere import PayHereProvider

        return PayHereProvider(
            merchant_id=settings.PAYHERE_MERCHANT_ID,
            merchant_secret=settings.PAYHERE_MERCHANT_SECRET,
            mode=settings.PAYHERE_MODE,
        )

    raise PaymentProviderError(f"Unsupported PAYMENT_PROVIDER '{provider}'")
