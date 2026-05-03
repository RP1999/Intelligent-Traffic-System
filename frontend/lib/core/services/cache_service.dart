import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

/// Offline cache service using SharedPreferences for local storage fallback.
/// Caches API responses so the app can display data when offline.
class CacheService {
  static final CacheService _instance = CacheService._internal();
  factory CacheService() => _instance;
  CacheService._internal();

  static const String _cachePrefix = 'cache_';
  static const String _timestampPrefix = 'cache_ts_';

  /// Default cache TTL: 1 hour
  static const Duration defaultTtl = Duration(hours: 1);

  /// Cache keys for each data type
  static const String keyDriverProfile = 'driver_profile';
  static const String keyJunctionScore = 'junction_score';
  static const String keyTrafficSummary = 'traffic_summary';
  static const String keyCommunityAlerts = 'community_alerts';
  static const String keyNotifications = 'notifications';
  static const String keyViolations = 'violations';
  static const String keyScoreHistory = 'score_history';
  static const String keyFines = 'fines';

  /// Store data in cache
  Future<void> put(String key, dynamic data, {Duration? ttl}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonStr = jsonEncode(data);
      await prefs.setString('$_cachePrefix$key', jsonStr);
      await prefs.setInt(
        '$_timestampPrefix$key',
        DateTime.now().millisecondsSinceEpoch,
      );
      debugPrint('[Cache] Stored: $key (${jsonStr.length} bytes)');
    } catch (e) {
      debugPrint('[Cache] Store error for $key: $e');
    }
  }

  /// Get cached data. Returns null if not found or expired.
  Future<dynamic> get(String key, {Duration? ttl}) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonStr = prefs.getString('$_cachePrefix$key');
      if (jsonStr == null) return null;

      // Check TTL
      final cachedAt = prefs.getInt('$_timestampPrefix$key') ?? 0;
      final maxAge = ttl ?? defaultTtl;
      final age = DateTime.now().millisecondsSinceEpoch - cachedAt;
      if (age > maxAge.inMilliseconds) {
        debugPrint('[Cache] Expired: $key (age: ${age ~/ 1000}s)');
        return null;
      }

      debugPrint('[Cache] Hit: $key (age: ${age ~/ 1000}s)');
      return jsonDecode(jsonStr);
    } catch (e) {
      debugPrint('[Cache] Read error for $key: $e');
      return null;
    }
  }

  /// Get cached data regardless of TTL (for offline fallback)
  Future<dynamic> getStale(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonStr = prefs.getString('$_cachePrefix$key');
      if (jsonStr == null) return null;
      debugPrint('[Cache] Stale hit: $key');
      return jsonDecode(jsonStr);
    } catch (e) {
      debugPrint('[Cache] Stale read error for $key: $e');
      return null;
    }
  }

  /// Check if cached data exists (regardless of TTL)
  Future<bool> has(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey('$_cachePrefix$key');
  }

  /// Remove specific cached entry
  Future<void> remove(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('$_cachePrefix$key');
    await prefs.remove('$_timestampPrefix$key');
  }

  /// Clear all cached data
  Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    final keys = prefs.getKeys();
    for (final key in keys) {
      if (key.startsWith(_cachePrefix) || key.startsWith(_timestampPrefix)) {
        await prefs.remove(key);
      }
    }
    debugPrint('[Cache] Cleared all entries');
  }

  /// Get cache timestamp for a key
  Future<DateTime?> getTimestamp(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final ts = prefs.getInt('$_timestampPrefix$key');
    if (ts == null) return null;
    return DateTime.fromMillisecondsSinceEpoch(ts);
  }

  /// Human-readable "last updated" string
  Future<String> getLastUpdated(String key) async {
    final ts = await getTimestamp(key);
    if (ts == null) return 'Never';
    final diff = DateTime.now().difference(ts);
    if (diff.inSeconds < 60) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }
}
