# Firebase Project Setup Guide

Follow these steps so every team member can connect to the **same** Firestore database.

---

## 1. Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project**
3. Name it (e.g. `intelligent-traffic-management`)
4. Disable Google Analytics (optional) → **Create project**

## 2. Enable Firestore

1. In the Firebase console sidebar, click **Build → Firestore Database**
2. Click **Create database**
3. Choose **Start in test mode** (you can lock down rules later)
4. Select the nearest region (e.g. `asia-south1` for Sri Lanka) → **Enable**

## 3. Generate a Service Account Key

1. Click the **⚙ gear icon** (top-left) → **Project settings**
2. Go to the **Service accounts** tab
3. Ensure **Firebase Admin SDK** is selected and language is **Python**
4. Click **Generate new private key** → **Generate key**
5. A JSON file will download (e.g. `intelligent-traffic-management-firebase-adminsdk-xxxxx.json`)

## 4. Place the Key in the Project

Rename the downloaded file to:

```
firebase-service-account.json
```

Copy it to:

```
backend/firebase-service-account.json
```

> **IMPORTANT:** This file contains secrets. It is already in `.gitignore`. **Never commit it to Git.** Each team member must get a copy from the project owner or download their own key from the Firebase console.

## 5. Share with Team Members

**Option A — Share the same key file:**
Send `firebase-service-account.json` to each team member via a secure channel (not Git). They place it at `backend/firebase-service-account.json`.

**Option B — Each member generates their own key:**
Add each team member to the Firebase project:
1. Firebase Console → **⚙ Project settings → Users and permissions**
2. Click **Add member**, enter their email, set role to **Editor**
3. Each member goes to **Service accounts → Generate new private key** and saves it as `backend/firebase-service-account.json`

## 6. Add Android App & Download `google-services.json`

This file is required for the Flutter mobile app (FCM push notifications, Firebase init).

1. In the Firebase console, click **⚙ gear icon → Project settings**
2. Scroll down to **Your apps** and click **Add app → Android**
3. Enter the Android package name: `com.itms.traffic_control_app`
4. (Optional) Enter app nickname: `ITMS Traffic Control`
5. Click **Register app**
6. Click **Download google-services.json**
7. Place the downloaded file at:

```
frontend/android/app/google-services.json
```

> **IMPORTANT:** This file must be from the **same** Firebase project as the backend service account key. If they point to different projects, FCM push notifications will not work.

## 7. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Key packages installed:
- `firebase-admin==6.6.0`
- `google-cloud-firestore>=2.16.0`

## 8. (Optional) Environment Variable

Instead of placing the JSON file at the default path, you can set:

```bash
set FIREBASE_SERVICE_ACCOUNT_PATH=C:\path\to\your\firebase-service-account.json
```

Or on Linux/Mac:
```bash
export FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/firebase-service-account.json
```

## 9. Verify the Setup

Start the backend server:

```bash
cd backend
uvicorn app.main:app --reload
```

If Firebase initializes correctly you'll see:
```
Firebase Admin SDK initialized
```

If the service account file is missing you'll see a warning — place the JSON file and restart.

---

## Firestore Collections

The app automatically creates these collections on first use:

| Collection | Purpose |
|---|---|
| `zones` | Parking/traffic zones |
| `violations` | Traffic violations |
| `drivers` | Driver scores & profiles |
| `driver_users` | Driver login accounts |
| `admin_users` | Admin login accounts |
| `parking_zones` | Parking zone configs |
| `audit_logs` | Admin audit trail |
| `dynamic_fines` | Fine records |
| `risk_scores` | Vehicle risk assessments |
| `abnormal_behavior` | Driving behavior logs |
| `driver_notifications` | Push notification records |
| `driver_fcm_tokens` | FCM device tokens |
| `lane_weaving_events` | Lane weaving detections |
| `junction_safety` | Junction safety scores |
| `community_alerts` | Community safety alerts |
| `emergency_status` | Emergency declarations |

## Firestore Security Rules (Production)

For production, go to **Firestore → Rules** and set:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only allow access from backend (Admin SDK bypasses rules)
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

The Firebase Admin SDK (used by the backend) **bypasses** security rules, so the backend will still work. This prevents direct client access.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `FileNotFoundError: firebase-service-account.json` | Place the JSON key file at `backend/firebase-service-account.json` |
| `google.auth.exceptions.DefaultCredentialsError` | Ensure the JSON file is valid and not corrupted |
| `PermissionDenied` | Check that Firestore is enabled in the Firebase console |
| `DeadlineExceeded` | Check internet connection; Firestore requires network access |
| Data not shared between members | Ensure everyone uses a key from the **same** Firebase project |
