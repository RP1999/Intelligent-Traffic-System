import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../models/analytics.dart';

/// State enum for data loading
enum LoadingState { initial, loading, loaded, error }

/// Provider for managing analytics data
class AnalyticsProvider extends ChangeNotifier {
  final ApiClient _apiClient = ApiClient();

  // State
  LoadingState _statsState = LoadingState.initial;
  LoadingState _trendsState = LoadingState.initial;
  LoadingState _hotspotsState = LoadingState.initial;
  String? _errorMessage;

  // Data
  DashboardStats? _stats;
  ViolationTrendsResponse? _trends;
  HotspotsResponse? _hotspots;

  // Trend period (days)
  int _trendPeriod = 7;

  // Getters
  LoadingState get statsState => _statsState;
  LoadingState get trendsState => _trendsState;
  LoadingState get hotspotsState => _hotspotsState;
  String? get errorMessage => _errorMessage;
  DashboardStats? get stats => _stats;
  ViolationTrendsResponse? get trends => _trends;
  HotspotsResponse? get hotspots => _hotspots;
  int get trendPeriod => _trendPeriod;

  /// Load all analytics data
  Future<void> loadAllAnalytics() async {
    await Future.wait([
      loadDashboardStats(),
      loadViolationTrends(),
      loadHotspots(),
    ]);
  }

  /// Load dashboard statistics
  Future<void> loadDashboardStats() async {
    _statsState = LoadingState.loading;
    notifyListeners();

    try {
      final response = await _apiClient.get(ApiEndpoints.dashboardStats);

      if (response.success && response.data != null) {
        _stats = DashboardStats.fromJson(response.data!);
        _statsState = LoadingState.loaded;
      } else {
        _errorMessage = response.error ?? 'Failed to load dashboard stats';
        _statsState = LoadingState.error;
      }
    } on UnauthorizedException {
      _errorMessage = 'Session expired. Please login again.';
      _statsState = LoadingState.error;
      rethrow;
    } catch (e) {
      _errorMessage = 'Error loading stats: $e';
      _statsState = LoadingState.error;
    }

    notifyListeners();
  }

  /// Load violation trends
  Future<void> loadViolationTrends({int? days}) async {
    if (days != null) _trendPeriod = days;
    
    _trendsState = LoadingState.loading;
    notifyListeners();

    try {
      final response = await _apiClient.get(
        ApiEndpoints.violationTrends,
        queryParams: {'days': _trendPeriod.toString()},
      );
