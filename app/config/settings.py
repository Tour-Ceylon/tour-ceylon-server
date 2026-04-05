import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
	clerk_jwks_url: str | None
	clerk_issuer: str | None
	clerk_audience: str | None
	cors_origins: list[str]
<<<<<<< Updated upstream
=======
	auto_create_tables: bool
>>>>>>> Stashed changes


def _parse_cors_origins(raw_value: str | None) -> list[str]:
	if not raw_value:
		return [
			"http://localhost:3000",
			"http://127.0.0.1:3000",
			"http://localhost:3001",
			"http://127.0.0.1:3001",
		]
	return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


<<<<<<< Updated upstream
=======
def _parse_auto_create_tables(raw_value: str | None) -> bool:
	"""Parse AUTO_CREATE_TABLES env var. Default False for safety in shared environments."""
	if raw_value is None:
		return False
	return raw_value.lower() in ("true", "1", "yes")


>>>>>>> Stashed changes
def get_settings() -> Settings:
	clerk_issuer = os.getenv("CLERK_ISSUER") or None
	clerk_jwks_url = os.getenv("CLERK_JWKS_URL")
	if not clerk_jwks_url and clerk_issuer:
		clerk_jwks_url = f"{clerk_issuer.rstrip('/')}/.well-known/jwks.json"

	return Settings(
		clerk_jwks_url=clerk_jwks_url,
		clerk_issuer=clerk_issuer,
		clerk_audience=os.getenv("CLERK_AUDIENCE") or None,
		cors_origins=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
<<<<<<< Updated upstream
=======
		auto_create_tables=_parse_auto_create_tables(os.getenv("AUTO_CREATE_TABLES")),
>>>>>>> Stashed changes
	)
