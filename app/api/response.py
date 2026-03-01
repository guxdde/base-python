from enum import Enum
from typing import Any, Optional
from fastapi.responses import JSONResponse


class ResponseCode(Enum):
    normal = 0
    param_error = 1
    auth_error = 2
    not_found = 3
    server_error = 500


error_massage = {
    ResponseCode.normal.value: "Success",
    ResponseCode.param_error.value: "Parameter error",
    ResponseCode.auth_error.value: "Authentication failed",
    ResponseCode.not_found.value: "Resource not found",
    ResponseCode.server_error.value: "Internal server error",
}


def success_response(data: Any = None, message: str = "ok") -> JSONResponse:
    return JSONResponse(
        content={
            "code": ResponseCode.normal.value,
            "message": message,
            "response": data,
        }
    )


def error_response(code: ResponseCode, message: Optional[str] = None) -> JSONResponse:
    msg = message or error_massage.get(code.value, "Unknown error")
    return JSONResponse(
        content={
            "code": code.value,
            "message": msg,
        }
    )
