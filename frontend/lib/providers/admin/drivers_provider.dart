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
  Driver? _selectedDriver;
  LoadingState _detailState = LoadingState.initial;

  // Getters
  LoadingState get state => _state;
  String? get errorMessage => _errorMessage;
  List<Driver> get drivers => _drivers;
  int get total => _total;
  int get currentPage => _currentPage;
  int get totalPages => (_total / _pageSize).ceil();
  bool get hasMore => _drivers.length < _total;
  String get sortBy => _sortBy;
  String get sortOrder => _sortOrder;
  Driver? get selectedDriver => _selectedDriver;
  LoadingState get detailState => _detailState;

  /// Load drivers with current sorting
  Future<void> loadDrivers({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 1;
      _drivers = [];
    }

    _state = _drivers.isEmpty ? LoadingState.loading : _state;
