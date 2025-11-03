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
