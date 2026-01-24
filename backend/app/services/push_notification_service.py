"""
Push Notification Service
Sends FCM push notifications to drivers via Firebase Admin SDK.

Usage:
    from app.services.push_notification_service import send_push_to_driver

    send_push_to_driver(
        plate_number="ABC-1234",
        title="New Violation",
        body="Speed violation detected at Main St.",
        data={"type": "violation", "violation_id": "v123"},
    )

Setup:
    1. Place Firebase Admin SDK service account JSON at:
       backend/firebase-service-account.json
    2. Or set FIREBASE_SERVICE_ACCOUNT_PATH env variable.
    3. Install: pip install firebase-admin
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Firebase Admin SDK (lazy-loaded)
_firebase_app = None

# Service account path
SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    str(Path(__file__).parent.parent.parent / "firebase-service-account.json"),
)


def _init_firebase():
    """Initialize Firebase Admin SDK if not already done."""
    global _firebase_app
    if _firebase_app is not None:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if Firebase was already initialized by another module
        # (e.g. firestore_client.py initializes it at startup)
        if firebase_admin._apps:
            _firebase_app = firebase_admin.get_app()
            logger.info("Firebase Admin SDK already initialized – reusing existing app.")
            return True

        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            logger.warning(
                "Firebase service account not found at %s. "
                "Push notifications are disabled.",
                SERVICE_ACCOUNT_PATH,
            )
            return False

        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized for push notifications.")
