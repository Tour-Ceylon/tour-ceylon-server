from fastapi import Request
from fastapi.responses import JSONResponse


class AdminAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def admin_api_error_handler(_: Request, exc: AdminAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message},
    )

