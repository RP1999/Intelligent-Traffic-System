"""
Firestore Client – single shared instance for the entire backend.

Initialises Firebase Admin SDK with a service-account JSON and exposes the
Firestore `db` reference plus small helpers used everywhere.

Setup:
    Place your Firebase service-account JSON at one of:
    1.  backend/firebase-service-account.json   (default)
    2.  Path set in  FIREBASE_SERVICE_ACCOUNT_PATH  env variable
"""

import os
import asyncio
import logging
from pathlib import Path
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from google.auth.credentials import AnonymousCredentials

logger = logging.getLogger(__name__)

_SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    str(Path(__file__).parent.parent.parent / "firebase-service-account.json"),
)


def _init_firebase() -> None:
    """Initialise Firebase Admin SDK (idempotent)."""
    if firebase_admin._apps:
        return  # already initialised
    if not os.path.exists(_SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(
            f"Firebase service-account JSON not found at {_SERVICE_ACCOUNT_PATH}.\n"
            "Download it from Firebase Console → Project Settings → Service Accounts."
        )
    cred = credentials.Certificate(_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialised (%s)", _SERVICE_ACCOUNT_PATH)


@lru_cache()
def get_firestore_db() -> AsyncClient:
    """Return a cached async Firestore client using Firebase Admin credentials."""
    _init_firebase()
    app = firebase_admin.get_app()
    cred = app.credential.get_credential()
    project_id = app.project_id
    return AsyncClient(project=project_id, credentials=cred)


# ---- convenience shortcuts used across the project ----

def get_db():
    """Alias kept short for import convenience."""
    return get_firestore_db()


def get_sync_db():
    """Return a cached synchronous Firestore client for use in sync/threaded code."""
    _init_firebase()
    return firestore.client()


def run_sync(coro):
    """Run an async coroutine from synchronous code.
    
    Tries to use the running event loop, falls back to creating a new one.
    Useful for services called from worker threads.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context — create a new thread loop
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# ---- Collection name constants (single source of truth) ----

class Collections:
    """Firestore collection names."""
    ZONES = "zones"
    VIOLATIONS = "violations"
    DRIVERS = "drivers"
    DRIVER_USERS = "driver_users"
    ADMIN_USERS = "admin_users"
    DRIVER_VIOLATIONS = "driver_violations"
    PARKING_ZONES = "parking_zones"
    AUDIT_LOGS = "audit_logs"
    DYNAMIC_FINES = "dynamic_fines"
    RISK_SCORES = "risk_scores"
    ABNORMAL_BEHAVIOR = "abnormal_behavior_log"
    DRIVER_NOTIFICATIONS = "driver_notifications"
    DRIVER_FCM_TOKENS = "driver_fcm_tokens"
    LANE_WEAVING_EVENTS = "lane_weaving_events"
    JUNCTION_SAFETY = "junction_safety"
    IOT_JUNCTION_STATUS = "iot_junction_status"
    JUNCTION_HISTORY = "junction_history"
    COMMUNITY_ALERTS = "community_alerts"
    EMERGENCY_STATUS = "emergency_status"
    CONFIG = "config"  # System configuration (stop line, etc.)
    SETTINGS = "settings"  # System settings (fines, penalties, thresholds)
