import logging
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

from app.database import make_engine
from app.errors import AppError
from app.routes import router
from app.schemas import ErrorResponse

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def error(status, code, message, details=None):
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": details or []}})


def create_app(engine=None):
    application = FastAPI(title="Pocket", description="Shared expenses and manually recorded repayments.",
        responses={code: {"model": ErrorResponse} for code in (404, 409, 422, 503)})
    application.state.engine = engine if engine is not None else make_engine()
    application.include_router(router)

    @application.exception_handler(AppError)
    async def business_error(_, exc):
        return error(exc.status, exc.code, exc.message)

    @application.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        details = [{"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
                   for item in exc.errors()]
        return error(422, "validation_error", "Check the submitted fields.", details)

    @application.exception_handler(HTTPException)
    async def http_error(_, exc):
        return error(exc.status_code, "http_error", str(exc.detail))

    @application.exception_handler(OperationalError)
    async def database_error(_, exc):
        code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
        if code & 255 in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            return error(503, "database_busy", "Pocket is busy. Retry shortly using the same request ID.")
        log.error("Database operation failed", exc_info=exc)
        return error(500, "internal_error", "Pocket could not complete this request.")

    @application.exception_handler(Exception)
    async def unexpected_error(_, exc):
        log.error("Unexpected application error", exc_info=exc)
        return error(500, "internal_error", "Pocket could not complete this request.")

    @application.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")
    return application


app = create_app()
