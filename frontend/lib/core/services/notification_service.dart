import 'dart:convert';
import 'dart:ui' show Color;
import 'package:flutter/foundation.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../network/api_client.dart';
import '../network/api_endpoints.dart';

/// Top-level handler for background FCM messages.
/// Must be a top-level function (not a class method).
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint('[FCM] Background message: ${message.messageId}');
  // Show local notification for background messages
  await NotificationService._showLocalNotification(message);

  // Attempt TTS for background messages so the driver hears the alert
  try {
    final tts = FlutterTts();
    await tts.setLanguage('en-US');
    await tts.setSpeechRate(0.5);
    await tts.setVolume(1.0);

    final data = message.data;
    String? spoken;
    if (data['type'] == 'violation') {
      final vtype = data['violation_type'] ?? 'Traffic';
      final fine = data['fine_amount'] ?? '';
      spoken = '$vtype violation detected.';
      if (fine.isNotEmpty && fine != '0') spoken = '$spoken Fine amount: $fine rupees.';
    } else if (data['type'] == 'warning') {
      final btype = (data['behavior_type'] ?? 'unknown').replaceAll('_', ' ');
      spoken = 'Warning. $btype detected.';
    } else if (message.notification?.body != null) {
      spoken = message.notification!.body!;
    }
    if (spoken != null) {
      await tts.speak(spoken);
    }
  } catch (e) {
    debugPrint('[FCM] Background TTS error (non-fatal): $e');
  }
}

/// Push notification service using Firebase Cloud Messaging (FCM).
/// Handles foreground, background, and terminated-state notifications.
class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();
  final ApiClient _apiClient = ApiClient();
  
  /// Text-to-Speech engine for audio notifications
  final FlutterTts _tts = FlutterTts();
  bool _ttsEnabled = true;
  bool _ttsInitialized = false;

  static const String _fcmTokenKey = 'fcm_token';
  static const String _ttsEnabledKey = 'tts_enabled';

  /// Android notification channel for traffic alerts
  static const AndroidNotificationChannel _channel = AndroidNotificationChannel(
    'itms_traffic_alerts',
    'Traffic Alerts',
    description: 'Notifications for violations, fines, and traffic updates',
    importance: Importance.high,
    playSound: true,
    enableVibration: true,
  );

  /// Callback for handling notification taps in the app
  Function(Map<String, dynamic>)? onNotificationTapped;

  /// Initialize FCM and local notifications
  Future<void> initialize() async {
    // Request permission (iOS & Android 13+)
    final settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
      announcement: false,
      carPlay: false,
      criticalAlert: false,
    );

    debugPrint('[FCM] Auth status: ${settings.authorizationStatus}');

    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('[FCM] Notification permission denied');
      return;
    }

    // Create Android notification channel
    await _localNotifications
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_channel);

    // Initialize local notifications
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _localNotifications.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
      onDidReceiveNotificationResponse: _onNotificationResponse,
    );

    // Tell Firebase to show notification banners even when the app is
    // in the foreground (iOS).  On Android we handle this ourselves via
    // flutter_local_notifications inside _handleForegroundMessage.
    await _messaging.setForegroundNotificationPresentationOptions(
      alert: true,
      badge: true,
      sound: true,
    );

    // Handle foreground messages
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // Handle notification taps when app is in background
    FirebaseMessaging.onMessageOpenedApp.listen(_handleNotificationTap);

    // Check if app was opened from a terminated state via notification
    final initialMessage = await _messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleNotificationTap(initialMessage);
    }

    // Get and register FCM token
    await _registerToken();

    // Listen for token refresh
    _messaging.onTokenRefresh.listen((newToken) {
      _sendTokenToServer(newToken);
    });
    
    // Initialize TTS
    await _initializeTts();

    debugPrint('[FCM] Notification service initialized');
  }
  
  /// Initialize Text-to-Speech engine
  Future<void> _initializeTts() async {
    try {
      // Load TTS preference
      final prefs = await SharedPreferences.getInstance();
      _ttsEnabled = prefs.getBool(_ttsEnabledKey) ?? true;
      
      // Configure TTS engine
      await _tts.setLanguage('en-US');
      await _tts.setSpeechRate(0.5); // Slower for clarity
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);
      
      _ttsInitialized = true;
      debugPrint('[TTS] Text-to-Speech initialized, enabled: $_ttsEnabled');
    } catch (e) {
      debugPrint('[TTS] Failed to initialize TTS: $e');
      _ttsInitialized = false;
    }
  }
  
  /// Enable or disable TTS for notifications
  Future<void> setTtsEnabled(bool enabled) async {
    _ttsEnabled = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_ttsEnabledKey, enabled);
    debugPrint('[TTS] Audio notifications ${enabled ? "enabled" : "disabled"}');
  }
  
  /// Get current TTS enabled status
  bool get isTtsEnabled => _ttsEnabled;
  
  /// Speak a notification message using TTS
  Future<void> speakNotification(String message) async {
    if (!_ttsEnabled || !_ttsInitialized) return;
    
    try {
      await _tts.stop(); // Stop any ongoing speech
      await _tts.speak(message);
      debugPrint('[TTS] Speaking: $message');
    } catch (e) {
      debugPrint('[TTS] Speak error: $e');
    }
  }
  
  /// Generate a spoken message for a violation notification
  String _generateViolationMessage(Map<String, dynamic> data) {
    final type = data['violation_type'] ?? 'Traffic';
    final fineAmount = data['fine_amount'] ?? '';
    
    // Map violation types to spoken messages
    final typeMessages = {
      'red_light': 'Red light violation detected',
      'speeding': 'Speeding violation detected',
      'parking': 'Parking violation detected',
      'no_parking': 'No parking zone violation',
      'illegal_parking': 'Illegal parking detected',
    };
    
    final spokenType = typeMessages[type.toString().toLowerCase()] ?? 
        '$type violation detected';
    
    if (fineAmount.isNotEmpty && fineAmount != '0') {
      return '$spokenType. Fine amount: $fineAmount rupees.';
    }
    return '$spokenType.';
  }

  /// Generate a spoken message for a warning notification
  String _generateWarningMessage(Map<String, dynamic> data) {
    final behaviorType = data['behavior_type'] ?? 'unknown';
    final severity = data['severity'] ?? '';
    final details = data['details'] ?? '';

    final typeMessages = {
      'sudden_stop': 'Warning. Sudden stop detected',
      'harsh_brake': 'Warning. Harsh braking detected',
      'lane_drift': 'Warning. Lane drifting detected',
      'wrong_way': 'Alert. Wrong way driving detected',
      'erratic_movement': 'Warning. Erratic movement detected',
      'parking_warning': 'Warning. Parking violation warning',
    };

    final spokenType = typeMessages[behaviorType] ??
        'Warning. ${behaviorType.replaceAll('_', ' ')} detected';

    final buffer = StringBuffer(spokenType);
    if (severity.isNotEmpty) {
      buffer.write('. Severity: $severity');
    }
    if (details.isNotEmpty) {
      buffer.write('. $details');
    }
    buffer.write('.');
    return buffer.toString();
  }

  /// Get the current FCM token
  Future<String?> getToken() async {
    try {
      return await _messaging.getToken();
    } catch (e) {
      debugPrint('[FCM] Token error: $e');
      return null;
    }
  }

  /// Register FCM token with the backend.
  /// Always sends to server even if the local cache matches, because
  /// a previous send may have silently failed (no auth, network error, etc.).
  Future<void> _registerToken() async {
    try {
      final token = await _messaging.getToken();
      if (token == null) {
        debugPrint('[FCM] No token available from Firebase');
        return;
      }
      debugPrint('[FCM] Got token: ${token.substring(0, 20)}…');
      await _sendTokenToServer(token);
    } catch (e) {
      debugPrint('[FCM] Token registration error: $e');
    }
  }

  /// Send FCM token to backend. Only caches locally on success.
  Future<void> _sendTokenToServer(String token) async {
    try {
      final response = await _apiClient.post(
        ApiEndpoints.registerFcmToken,
        body: {'fcm_token': token, 'platform': defaultTargetPlatform.name},
      );
      if (response.success) {
        // Only cache after the server confirms receipt
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_fcmTokenKey, token);
        debugPrint('[FCM] Token sent to server successfully');
      } else {
        debugPrint('[FCM] Server rejected token: ${response.error}');
      }
    } catch (e) {
      debugPrint('[FCM] Send token error (will retry next launch): $e');
    }
  }

  /// Handle foreground messages - show local notification and speak if violation
  void _handleForegroundMessage(RemoteMessage message) {
    debugPrint('[FCM] Foreground message: ${message.notification?.title}');
    _showLocalNotification(message);
    
    // Speak notifications using TTS based on type
    final data = message.data;
    if (data['type'] == 'violation') {
      final spokenMessage = _generateViolationMessage(data);
      speakNotification(spokenMessage);
    } else if (data['type'] == 'warning') {
      final spokenMessage = _generateWarningMessage(data);
      speakNotification(spokenMessage);
    } else if (data['type'] == 'fine') {
      final amount = data['amount'] ?? '';
      speakNotification('Fine issued. Amount: $amount rupees.');
    } else if (data['type'] == 'score_update') {
      final score = data['score'] ?? '';
      final risk = data['risk_level'] ?? '';
      speakNotification('Safety score updated. Your score is now $score. Risk level: $risk.');
    } else if (message.notification?.body != null) {
      // For other notification types, speak the body
      speakNotification(message.notification!.body!);
    }
  }

  /// Handle notification tap (app in background/terminated)
  void _handleNotificationTap(RemoteMessage message) {
    debugPrint('[FCM] Notification tapped: ${message.data}');
    onNotificationTapped?.call(message.data);
  }

  /// Handle tap on local notification
  void _onNotificationResponse(NotificationResponse response) {
    if (response.payload != null) {
      try {
        final data = jsonDecode(response.payload!) as Map<String, dynamic>;
        onNotificationTapped?.call(data);
      } catch (_) {}
    }
  }

  /// Show a real phone system notification (appears in the phone's
  /// notification shade just like WhatsApp, Instagram, etc.).
  ///
  /// Works for both foreground and background/terminated states, and
  /// handles FCM messages with or without a `notification` payload.
  static Future<void> _showLocalNotification(RemoteMessage message) async {
    final localNotif = FlutterLocalNotificationsPlugin();

    // Initialize plugin (needed each time for background isolate)
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    await localNotif.initialize(
      const InitializationSettings(
        android: androidInit,
        iOS: DarwinInitializationSettings(
          requestAlertPermission: true,
          requestBadgePermission: true,
          requestSoundPermission: true,
        ),
      ),
    );

    // Ensure the notification channel exists (required for Android 8+).
    // Channels persist on the device, so this is a safe idempotent call.
    await localNotif
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_channel);

    // Build title & body: prefer the FCM notification payload, but fall
    // back to constructing from the data payload so data-only messages
    // also produce a visible phone notification.
    final notification = message.notification;
    String title = notification?.title ?? '';
    String body = notification?.body ?? '';

    if (title.isEmpty || body.isEmpty) {
      final data = message.data;
      final type = data['type'] ?? '';
      switch (type) {
        case 'violation':
          final vtype = data['violation_type'] ?? 'Traffic';
          final fine = data['fine_amount'] ?? '';
          title = title.isEmpty ? 'Traffic Violation Detected' : title;
          body = body.isEmpty
              ? '$vtype — Fine: LKR $fine'
              : body;
          break;
        case 'warning':
          final btype = (data['behavior_type'] ?? 'unknown')
              .replaceAll('_', ' ')
              .split(' ')
              .map((w) => w.isNotEmpty
                  ? '${w[0].toUpperCase()}${w.substring(1)}'
                  : w)
              .join(' ');
          title = title.isEmpty ? 'Driving Warning' : title;
          body = body.isEmpty
              ? '$btype detected. Severity: ${(data['severity'] ?? '').toUpperCase()}'
              : body;
          break;
        case 'fine':
          title = title.isEmpty ? 'Fine Issued' : title;
          body = body.isEmpty
              ? 'Amount: LKR ${data['amount'] ?? '0'}'
              : body;
          break;
        case 'score_update':
          title = title.isEmpty ? 'Safety Score Updated' : title;
          body = body.isEmpty
              ? 'Your score is now ${data['score'] ?? '?'} (${data['risk_level'] ?? ''})'
              : body;
          break;
        default:
          title = title.isEmpty ? 'Traffic Alert' : title;
          body = body.isEmpty ? 'You have a new notification' : body;
      }
    }

    // Use a unique-enough ID so each message produces its own notification
    final notifId = message.messageId?.hashCode ??
        DateTime.now().millisecondsSinceEpoch ~/ 1000;

    await localNotif.show(
      notifId,
      title,
      body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _channel.id,
          _channel.name,
          channelDescription: _channel.description,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
          color: const Color(0xFFFFD700),
          playSound: true,
          enableVibration: true,
          // Show as a heads-up notification (banner at top of screen)
          fullScreenIntent: false,
          visibility: NotificationVisibility.public,
          category: AndroidNotificationCategory.message,
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: jsonEncode(message.data),
    );
  }

  /// Subscribe to a topic (e.g., junction-specific alerts)
  Future<void> subscribeToTopic(String topic) async {
    try {
      await _messaging.subscribeToTopic(topic);
      debugPrint('[FCM] Subscribed to topic: $topic');
    } catch (e) {
      debugPrint('[FCM] Subscribe error: $e');
    }
  }

  /// Unsubscribe from a topic
  Future<void> unsubscribeFromTopic(String topic) async {
    try {
      await _messaging.unsubscribeFromTopic(topic);
      debugPrint('[FCM] Unsubscribed from topic: $topic');
    } catch (e) {
      debugPrint('[FCM] Unsubscribe error: $e');
    }
  }

  /// Clear stored token (on logout)
  Future<void> clearToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_fcmTokenKey);
      await _messaging.deleteToken();
      debugPrint('[FCM] Token cleared');
    } catch (e) {
      debugPrint('[FCM] Clear token error: $e');
    }
  }
}
