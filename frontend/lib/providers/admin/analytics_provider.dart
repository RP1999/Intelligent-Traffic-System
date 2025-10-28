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
