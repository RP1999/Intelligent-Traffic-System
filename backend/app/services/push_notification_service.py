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
        return True
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin SDK: %s", e)
        return False


def _get_fcm_token(plate_number: str) -> Optional[str]:
    """Look up the FCM token for a driver by plate number from Firestore (sync)."""
    try:
        from app.db.firestore_client import get_sync_db, Collections
        from app.utils.plate_utils import normalize_plate

        norm_plate = normalize_plate(plate_number)
        db = get_sync_db()
        # Try normalized plate first, then original
        for plate_val in dict.fromkeys([norm_plate, plate_number]):
            if not plate_val:
                continue
            doc = db.collection(Collections.DRIVER_FCM_TOKENS).document(plate_val).get()
            if doc.exists:
                return doc.to_dict().get("fcm_token")
        return None
    except Exception as e:
        logger.error("Error fetching FCM token for %s: %s", plate_number, e)
        return None


def send_push_to_driver(
    plate_number: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """
    Send a push notification to a specific driver (synchronous).

    Args:
        plate_number: Driver's license plate (used to look up FCM token).
        title: Notification title.
        body: Notification body text.
        data: Optional data payload (all values must be strings).

    Returns:
        True if notification was sent successfully, False otherwise.
    """
    if not _init_firebase():
        logger.warning("Firebase not configured – skipping push to %s", plate_number)
        return False

    token = _get_fcm_token(plate_number)
    if not token:
        logger.info("No FCM token registered for plate %s", plate_number)
        return False

    try:
        from firebase_admin import messaging

        # Ensure all data values are strings (FCM requirement)
        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=str_data,
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="itms_traffic_alerts",
                    icon="ic_notification",
                    color="#FFD700",
                    sound="default",
                ),
            ),
        )

        response = messaging.send(message)
        logger.info("Push sent to %s: %s", plate_number, response)
        return True

    except Exception as e:
        logger.error("Failed to send push to %s: %s", plate_number, e)
        return False


def send_violation_notification(
    plate_number: str,
    violation_type: str,
    fine_amount: float,
    violation_id: str = "",
) -> bool:
    """Send a push notification for a new violation (synchronous)."""
    return send_push_to_driver(
        plate_number=plate_number,
        title="Traffic Violation Detected",
        body=f"{violation_type} — Fine: LKR {fine_amount:,.0f}",
        data={
            "type": "violation",
            "violation_id": violation_id,
            "violation_type": violation_type,
            "fine_amount": str(fine_amount),
        },
    )


def send_fine_notification(
    plate_number: str,
    fine_id: int,
    amount: float,
    due_date: str = "",
) -> bool:
    """Send a push notification for a new or updated fine (synchronous)."""
    return send_push_to_driver(
        plate_number=plate_number,
        title="Fine Issued",
