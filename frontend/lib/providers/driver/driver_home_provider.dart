import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/services/cache_service.dart';
import '../../models/driver_profile.dart';
import '../../models/community.dart';

/// Loading state enum
enum DriverHomeState { idle, loading, loaded, error }

/// Provider for Driver Home screen data
class DriverHomeProvider with ChangeNotifier {
  final ApiClient _apiClient = ApiClient();
  final CacheService _cache = CacheService();

  DriverHomeState _state = DriverHomeState.idle;
  DriverProfile? _profile;
  JunctionScore? _junctionScore;
  TrafficSummary? _trafficSummary;
  List<CommunityAlert> _alerts = [];
  List<DriverNotification> _notifications = [];
  int _unreadCount = 0;
  String? _error;
  bool _isOffline = false;
  Timer? _liveTimer;
  static const _liveRefreshInterval = Duration(seconds: 15);

  // Getters
  DriverHomeState get state => _state;
  DriverProfile? get profile => _profile;
  JunctionScore? get junctionScore => _junctionScore;
  TrafficSummary? get trafficSummary => _trafficSummary;
  List<CommunityAlert> get alerts => _alerts;
  List<DriverNotification> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  String? get error => _error;
  bool get isLoading => _state == DriverHomeState.loading;
  bool get isOffline => _isOffline;

  /// Load all home screen data in parallel.
  /// On failure, falls back to cached data.
  Future<void> loadHomeData() async {
    _state = DriverHomeState.loading;
    _error = null;
    _isOffline = false;
    notifyListeners();

    try {
      // Fire all requests in parallel
      await Future.wait([
        _loadProfile(),
        _loadJunctionScore(),
        _loadTrafficSummary(),
        _loadAlerts(),
        _loadNotifications(),
      ], eagerError: false);

      _state = DriverHomeState.loaded;
    } catch (e) {
      // Network error — try loading from cache
      _isOffline = true;
      await _loadFromCache();
      if (_profile != null) {
        _state = DriverHomeState.loaded;
        _error = 'Showing cached data (offline)';
      } else {
        _state = DriverHomeState.error;
        _error = 'No connection and no cached data available';
      }
    }
    notifyListeners();
  }

  /// Load all data from cache (offline fallback)
  Future<void> _loadFromCache() async {
    try {
      final profileData = await _cache.getStale(CacheService.keyDriverProfile);
      if (profileData != null) {
        _profile = DriverProfile.fromJson(Map<String, dynamic>.from(profileData));
      }

      final junctionData = await _cache.getStale(CacheService.keyJunctionScore);
      if (junctionData != null) {
        _junctionScore = JunctionScore.fromJson(Map<String, dynamic>.from(junctionData));
      }

      final trafficData = await _cache.getStale(CacheService.keyTrafficSummary);
      if (trafficData != null) {
        _trafficSummary = TrafficSummary.fromJson(Map<String, dynamic>.from(trafficData));
      }

      final alertsData = await _cache.getStale(CacheService.keyCommunityAlerts);
      if (alertsData != null) {
        final alertsList = (alertsData as List?)?.cast<Map<String, dynamic>>() ?? [];
        _alerts = alertsList.map((a) => CommunityAlert.fromJson(a)).toList();
      }

      final notifData = await _cache.getStale(CacheService.keyNotifications);
      if (notifData != null) {
        final notifMap = Map<String, dynamic>.from(notifData);
        final notifList = (notifMap['notifications'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        _notifications = notifList.map((n) => DriverNotification.fromJson(n)).toList();
        _unreadCount = notifMap['unread_count'] ?? 0;
      }
    } catch (e) {
      debugPrint('[DriverHome] Cache load error: $e');
    }
  }

  Future<void> _loadProfile() async {
    try {
      final response = await _apiClient.get(ApiEndpoints.driverProfile);
      final data = response.data;
      if (response.success && data != null) {
        _profile = DriverProfile.fromJson(data);
        // Cache the response
        await _cache.put(CacheService.keyDriverProfile, data);
      }
    } catch (e) {
      debugPrint('[DriverHome] Profile load error: $e');
      // Try cache fallback
      final cached = await _cache.getStale(CacheService.keyDriverProfile);
      if (cached != null && _profile == null) {
        _profile = DriverProfile.fromJson(Map<String, dynamic>.from(cached));
      }
    }
  }

  Future<void> _loadJunctionScore() async {
    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.junctionScore}?junction_id=main',
      );
      final data = response.data;
      if (response.success && data != null) {
        _junctionScore = JunctionScore.fromJson(data);
        await _cache.put(CacheService.keyJunctionScore, data);
      }
    } catch (e) {
      debugPrint('[DriverHome] Junction score error: $e');
      final cached = await _cache.getStale(CacheService.keyJunctionScore);
      if (cached != null && _junctionScore == null) {
        _junctionScore = JunctionScore.fromJson(Map<String, dynamic>.from(cached));
      }
    }
  }

  Future<void> _loadTrafficSummary() async {
    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.trafficSummary}?junction_id=main',
      );
      final data = response.data;
      if (response.success && data != null) {
        _trafficSummary = TrafficSummary.fromJson(data);
        await _cache.put(CacheService.keyTrafficSummary, data);
      }
    } catch (e) {
      debugPrint('[DriverHome] Traffic summary error: $e');
      final cached = await _cache.getStale(CacheService.keyTrafficSummary);
      if (cached != null && _trafficSummary == null) {
        _trafficSummary = TrafficSummary.fromJson(Map<String, dynamic>.from(cached));
      }
    }
  }

  Future<void> _loadAlerts() async {
    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.communityAlerts}?limit=10',
      );
      final data = response.data;
      if (response.success && data != null) {
        final alertsList = data['alerts'] as List? ?? [];
        _alerts = alertsList
            .map((a) => CommunityAlert.fromJson(a as Map<String, dynamic>))
            .toList();
        // Cache the alerts list
        await _cache.put(CacheService.keyCommunityAlerts, alertsList);
      }
    } catch (e) {
      debugPrint('[DriverHome] Alerts error: $e');
      final cached = await _cache.getStale(CacheService.keyCommunityAlerts);
      if (cached != null && _alerts.isEmpty) {
        final list = (cached as List?)?.cast<Map<String, dynamic>>() ?? [];
        _alerts = list.map((a) => CommunityAlert.fromJson(a)).toList();
      }
    }
  }

  Future<void> _loadNotifications() async {
    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.myNotifications}?limit=20',
      );
      final data = response.data;
      if (response.success && data != null) {
        final notifList = data['notifications'] as List? ?? [];
        _notifications = notifList
            .map((n) => DriverNotification.fromJson(n as Map<String, dynamic>))
            .toList();
        _unreadCount = data['unread_count'] ?? 0;
        // Cache full response
        await _cache.put(CacheService.keyNotifications, data);
      }
    } catch (e) {
      debugPrint('[DriverHome] Notifications error: $e');
      final cached = await _cache.getStale(CacheService.keyNotifications);
      if (cached != null && _notifications.isEmpty) {
        final notifMap = Map<String, dynamic>.from(cached);
        final notifList = (notifMap['notifications'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        _notifications = notifList.map((n) => DriverNotification.fromJson(n)).toList();
        _unreadCount = notifMap['unread_count'] ?? 0;
      }
    }
  }

  /// Mark a notification as read
  Future<void> markNotificationRead(String notificationId) async {
    try {
      await _apiClient.post(
        '/driver/notifications/$notificationId/read',
      );
      final idx = _notifications.indexWhere(
        (n) => n.notificationId == notificationId,
      );
      if (idx != -1) {
        _unreadCount = (_unreadCount - 1).clamp(0, _notifications.length);
        // Update local notification to mark as read
        _notifications[idx] = DriverNotification(
          notificationId: _notifications[idx].notificationId,
          title: _notifications[idx].title,
          message: _notifications[idx].message,
          notificationType: _notifications[idx].notificationType,
          timestamp: _notifications[idx].timestamp,
          read: true,
        );
        notifyListeners();
      }
    } catch (e) {
      debugPrint('[DriverHome] Mark read error: $e');
    }
  }

  /// Refresh all data
  Future<void> refresh() => loadHomeData();

  /// Start auto-refreshing live data (junction safety, traffic summary)
  void startLivePolling() {
    _liveTimer?.cancel();
    _liveTimer = Timer.periodic(_liveRefreshInterval, (_) => _refreshLiveData());
  }

  /// Stop auto-refreshing
  void stopLivePolling() {
    _liveTimer?.cancel();
    _liveTimer = null;
  }

  /// Refresh only live/real-time data without resetting the full state
  Future<void> _refreshLiveData() async {
    try {
      await Future.wait([
        _loadJunctionScore(),
        _loadTrafficSummary(),
        _loadNotifications(),
        _loadAlerts(),
      ], eagerError: false);
      notifyListeners();
    } catch (e) {
      debugPrint('[DriverHome] Live refresh error: $e');
    }
  }

  @override
  void dispose() {
    _liveTimer?.cancel();
    super.dispose();
  }
}
