from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


def http_exception_from(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NotImplementedError):
        return HTTPException(status_code=501, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (ConnectionError, OSError)):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, SQLAlchemyError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _json_response(exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if not isinstance(detail, str):
        detail = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return _json_response(http_exception_from(exc))

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(
        _request: Request, exc: FileNotFoundError
    ) -> JSONResponse:
        return _json_response(http_exception_from(exc))

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        _request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        return _json_response(http_exception_from(exc))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        return _json_response(http_exception_from(exc))
