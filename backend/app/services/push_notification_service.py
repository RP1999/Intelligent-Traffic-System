"""
Push Notification Service
Sends FCM push notifications to drivers via Firebase Admin SDK.

Usage:
    from app.services.push_notification_service import send_push_to_driver

    send_push_to_driver(
        plate_number="ABC-1234",
