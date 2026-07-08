"""
FastAPI application entry point.

Sets up CORS, rate limiting, request size caps, routes, and Whisper model
pre-loading at startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.routes.assess import router as assess_router
from app.services.whisper_service import preload_model

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit],
)


# ---------------------------------------------------------------------------
# Lifespan — pre-load Whisper model
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the Whisper model on startup to avoid first-request latency."""
    logger.info("Starting up — pre-loading Whisper model…")
    preload_model()
    logger.info("Whisper model loaded. Server ready.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Pronunciation Assessment API",
    description=(
        "Upload a 30-45 second English audio clip and receive pronunciation scores "
        "with word-level highlighted mistakes and plain-English explanations."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow all origins for MVP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request size middleware — reject bodies > MAX_UPLOAD_SIZE_MB
# ---------------------------------------------------------------------------
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject requests with bodies larger than the configured limit."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
            if size > settings.max_upload_size_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "request_too_large",
                        "detail": (
                            f"Request body ({size / (1024*1024):.1f} MB) exceeds "
                            f"the {settings.max_upload_size_mb} MB limit."
                        ),
                    },
                )
        except ValueError:
            pass
    return await call_next(request)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(assess_router)


# Health check
@app.get("/api/health", tags=["health"])
async def health_check():
    """Health check endpoint — confirms the server is running."""
    return {"status": "healthy", "version": "1.0.0"}
