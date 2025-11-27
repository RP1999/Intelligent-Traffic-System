import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../models/driver.dart';

/// State enum for data loading
enum LoadingState { initial, loading, loaded, error }

/// Provider for managing drivers data
class DriversProvider extends ChangeNotifier {
  final ApiClient _apiClient = ApiClient();

  // State
  LoadingState _state = LoadingState.initial;
  String? _errorMessage;
  List<Driver> _drivers = [];
  int _total = 0;
  int _currentPage = 1;
  final int _pageSize = 20;

  // Sorting
  String _sortBy = 'current_score';
  String _sortOrder = 'asc';

  // Search
  String _searchQuery = '';

  // Selected driver for detail view
