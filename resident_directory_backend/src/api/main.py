"""
FastAPI application entrypoint for the Resident Directory Backend.

Flow: ApplicationBootstrapFlow
- Configures logging
- Creates FastAPI app with OpenAPI metadata
- Configures CORS for the Next.js frontend
- Registers all route modules
- Provides health check endpoint

Contract:
  Input: Environment variables for CORS, DB connection, JWT settings
  Output: Running FastAPI application on configured port
  Errors: Startup failures logged; individual route errors handled per-route
  Side effects: Database connections, audit logging

Observability:
  - Structured logging to stdout
  - Health check at GET /
  - Full OpenAPI docs at /docs and /openapi.json
"""

import logging
import os

from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_auth import router as auth_router
from src.api.routes_residents import router as residents_router
from src.api.routes_announcements import router as announcements_router
from src.api.routes_emergency_contacts import router as emergency_contacts_router
from src.api.routes_audit import router as audit_router

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- OpenAPI tags for documentation grouping ---
openapi_tags = [
    {
        "name": "Health",
        "description": "Application health check endpoint.",
    },
    {
        "name": "Authentication",
        "description": "User authentication, registration, and profile management.",
    },
    {
        "name": "Residents",
        "description": "Resident profile CRUD, search, pagination, CSV import/export.",
    },
    {
        "name": "Announcements",
        "description": "Community announcement management.",
    },
    {
        "name": "Emergency Contacts",
        "description": "Emergency contact management for residents.",
    },
    {
        "name": "Audit Logs",
        "description": "Audit trail retrieval for admin review.",
    },
]

# --- FastAPI app ---
app = FastAPI(
    title="Resident Directory API",
    description=(
        "REST API for the Community Resident Management System. "
        "Provides resident profiles, authentication, announcements, "
        "emergency contacts, audit logging, and CSV import/export."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# --- CORS configuration ---
# Read allowed origins from env; fall back to permissive defaults for development
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

allowed_methods_str = os.getenv("ALLOWED_METHODS", "GET,POST,PUT,DELETE,PATCH,OPTIONS")
allowed_methods = [m.strip() for m in allowed_methods_str.split(",") if m.strip()]

allowed_headers_str = os.getenv("ALLOWED_HEADERS", "Content-Type,Authorization,X-Requested-With")
allowed_headers = [h.strip() for h in allowed_headers_str.split(",") if h.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
)

# --- Register routers ---
app.include_router(auth_router)
app.include_router(residents_router)
app.include_router(announcements_router)
app.include_router(emergency_contacts_router)
app.include_router(audit_router)


# --- Health check ---
# PUBLIC_INTERFACE
@app.get(
    "/",
    tags=["Health"],
    summary="Health Check",
    description="Returns application health status. Use this to verify the API is running.",
)
def health_check():
    """
    Health check endpoint.

    Returns a simple JSON object confirming the service is operational.
    """
    return {"status": "healthy", "service": "resident-directory-backend", "version": "1.0.0"}


logger.info("Resident Directory Backend initialized. Routes registered.")
