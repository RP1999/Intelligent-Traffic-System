import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/services/cache_service.dart';
import '../../models/violation.dart';
import '../../models/community.dart';

/// Loading state
enum ViolationLoadState { idle, loading, loaded, error }

/// Provider for driver's personal violations
class DriverViolationsProvider with ChangeNotifier {
  final ApiClient _apiClient = ApiClient();
  final CacheService _cache = CacheService();

  ViolationLoadState _state = ViolationLoadState.idle;
  List<Violation> _violations = [];
  int _total = 0;
  int _offset = 0;
  final int _limit = 20;
  bool _hasMore = true;
  String? _error;
  bool _isOffline = false;

  // Score history
  int _currentScore = 100;
  String _trend = 'stable';
  List<ScoreHistoryEntry> _scoreHistory = [];

  // Getters
  ViolationLoadState get state => _state;
  List<Violation> get violations => _violations;
  int get total => _total;
  bool get hasMore => _hasMore;
  String? get error => _error;
  bool get isLoading => _state == ViolationLoadState.loading;
  int get currentScore => _currentScore;
  String get trend => _trend;
  List<ScoreHistoryEntry> get scoreHistory => _scoreHistory;
  bool get isOffline => _isOffline;

  /// Load violations (initial load)
  Future<void> loadViolations({bool refresh = false}) async {
    if (refresh) {
      _violations.clear();
      _offset = 0;
      _hasMore = true;
    }

    if (!_hasMore && !refresh) return;

    _state = ViolationLoadState.loading;
    _error = null;
    _isOffline = false;
    notifyListeners();

    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.myViolations}?limit=$_limit&offset=$_offset',
      );

      if (response.success && response.data != null) {
        final data = response.data!;
        final violationsList = data['violations'] as List? ?? [];
        final newViolations = violationsList
            .map((v) => Violation.fromJson(v as Map<String, dynamic>))
            .toList();

        _violations.addAll(newViolations);
        _total = data['total'] ?? _violations.length;
        _offset += newViolations.length;
        _hasMore = newViolations.length >= _limit;
        _state = ViolationLoadState.loaded;

        // Cache the full violations list on refresh
        if (refresh || _offset <= _limit) {
          await _cache.put(CacheService.keyViolations, data);
        }
      } else {
        _state = ViolationLoadState.error;
        _error = 'Failed to load violations';
      }
    } catch (e) {
      // Offline fallback
      if (_violations.isEmpty) {
        _isOffline = true;
        final cached = await _cache.getStale(CacheService.keyViolations);
        if (cached != null) {
          final data = Map<String, dynamic>.from(cached);
          final violationsList = data['violations'] as List? ?? [];
          _violations = violationsList
              .map((v) => Violation.fromJson(Map<String, dynamic>.from(v)))
              .toList();
          _total = data['total'] ?? _violations.length;
          _hasMore = false;
          _state = ViolationLoadState.loaded;
          _error = 'Showing cached data (offline)';
        } else {
          _state = ViolationLoadState.error;
          _error = 'No connection and no cached data';
        }
      } else {
        _state = ViolationLoadState.error;
        _error = e.toString();
      }
    }
    notifyListeners();
  }

  /// Load more violations (pagination)
  Future<void> loadMore() async {
    if (_state == ViolationLoadState.loading || !_hasMore) return;
    await loadViolations();
  }

  /// Load score history
  Future<void> loadScoreHistory({int days = 30}) async {
    try {
      final response = await _apiClient.get(
        '${ApiEndpoints.scoreHistory}?days=$days',
      );
      if (response.success && response.data != null) {
        final data = response.data!;
        _currentScore = data['current_score'] ?? 100;
        _trend = data['trend'] ?? 'stable';
        final historyList = data['history'] as List? ?? [];
        _scoreHistory = historyList
            .map((h) => ScoreHistoryEntry.fromJson(h as Map<String, dynamic>))
            .toList();
        // Cache score history
        await _cache.put(CacheService.keyScoreHistory, data);
        notifyListeners();
      }
    } catch (e) {
      debugPrint('[DriverViolations] Score history error: $e');
      // Offline fallback
      final cached = await _cache.getStale(CacheService.keyScoreHistory);
      if (cached != null && _scoreHistory.isEmpty) {
        final data = Map<String, dynamic>.from(cached);
        _currentScore = data['current_score'] ?? 100;
        _trend = data['trend'] ?? 'stable';
        final historyList = data['history'] as List? ?? [];
        _scoreHistory = historyList
            .map((h) => ScoreHistoryEntry.fromJson(Map<String, dynamic>.from(h)))
            .toList();
        notifyListeners();
      }
    }
  }

  /// Refresh all data
  Future<void> refresh() async {
    await Future.wait([
      loadViolations(refresh: true),
      loadScoreHistory(),
    ]);
  }
}
