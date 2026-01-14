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
