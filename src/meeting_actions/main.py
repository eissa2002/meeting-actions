import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from meeting_actions.config import load_settings
from meeting_actions.extractor import ExtractionError, Extractor, OpenAICompatibleExtractor
from meeting_actions.models import (
    MAX_NOTES_CHARS,
    ErrorDetail,
    ErrorResponse,
    ExtractRequest,
    ExtractResponse,
)

logger = logging.getLogger("meeting_actions")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message)


async def handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    # Rejected before the route runs, so log the outcome here. Never echo or log the body.
    logger.info("extract outcome=invalid_request")
    return error_response(
        400, "invalid_request", "Request body must be JSON with a 'notes' string field."
    )


def create_app(extractor: Extractor | None = None) -> FastAPI:
    if extractor is None:
        # Production path: fail at startup if any LLM_* variable is missing.
        logging.basicConfig(level=logging.INFO)
        extractor = OpenAICompatibleExtractor.from_settings(load_settings())

    app = FastAPI(title="Meeting Actions API", version="1.0.0")
    app.state.extractor = extractor
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/action-items")
    def extract_action_items(body: ExtractRequest, request: Request) -> ExtractResponse:
        notes = body.notes.strip()
        current: Extractor = request.app.state.extractor
        start = time.perf_counter()
        outcome = "ok"
        items_count = 0
        try:
            if not notes:
                raise AppError(400, "empty_notes", "Notes must not be empty.")
            if len(notes) > MAX_NOTES_CHARS:
                raise AppError(
                    400,
                    "notes_too_long",
                    f"Notes must be at most {MAX_NOTES_CHARS:,} characters; "
                    f"received {len(notes):,}.",
                )
            items = current.extract(notes)
            items_count = len(items)
            return ExtractResponse(action_items=items)
        except AppError as exc:
            outcome = exc.code
            raise
        except ExtractionError as exc:
            outcome = "extraction_failed"
            raise AppError(
                502, "extraction_failed", "Could not extract action items. Please try again."
            ) from exc
        finally:
            # Never log the notes text (FR-012).
            logger.info(
                "extract outcome=%s notes_chars=%d items=%d latency_ms=%d",
                outcome,
                len(notes),
                items_count,
                (time.perf_counter() - start) * 1000,
            )

    return app
