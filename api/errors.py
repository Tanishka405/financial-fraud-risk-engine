"""Consistent error envelope: {"error": {"code", "message", "details"}}."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        self.status, self.code, self.message, self.details = status, code, message, details


def _resp(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return _resp(e.status, e.code, e.message, e.details)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, e: RequestValidationError):
        det = [{"field": ".".join(str(p) for p in x["loc"][1:]) or str(x["loc"][0]), "message": x["msg"]} for x in e.errors()]
        return _resp(422, "VALIDATION_ERROR", "Request parameters failed validation.", det)

    @app.exception_handler(HTTPException)
    async def _http(_: Request, e: HTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE"}.get(e.status_code, "HTTP_ERROR")
        return _resp(e.status_code, code, str(e.detail))

    @app.exception_handler(Exception)
    async def _any(_: Request, e: Exception):  # never leak stack traces / paths
        return _resp(500, "INTERNAL_ERROR", "An unexpected error occurred.")
