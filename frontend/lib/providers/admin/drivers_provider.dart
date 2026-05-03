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

  // Risk level filter
  String _riskFilter = 'all'; // all, excellent, good, fair, poor, critical

  // Registered users filter
  bool _registeredOnly = true; // Show only registered drivers by default

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
  String get riskFilter => _riskFilter;
  bool get registeredOnly => _registeredOnly;
  Driver? get selectedDriver => _selectedDriver;
  LoadingState get detailState => _detailState;

  /// Load drivers with current sorting
  Future<void> loadDrivers({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 1;
      _drivers = [];
    }

    _state = _drivers.isEmpty ? LoadingState.loading : _state;
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, dynamic>{
        'limit': _pageSize.toString(),
        'offset': ((_currentPage - 1) * _pageSize).toString(),
        'sort_by': _sortBy,
        'order': _sortOrder,
        'registered_only': _registeredOnly.toString(),
      };

      if (_searchQuery.trim().isNotEmpty) {
        queryParams['search'] = _searchQuery.trim();
      }

      if (_riskFilter != 'all') {
        queryParams['risk_level'] = _riskFilter;
      }

      final response = await _apiClient.get(
        ApiEndpoints.allDrivers,
        queryParams: queryParams,
      );

      if (response.success && response.data != null) {
        final parsed = DriversResponse.fromJson(response.data!);

        if (refresh) {
          _drivers = parsed.drivers;
        } else {
          _drivers.addAll(parsed.drivers);
        }
        _total = parsed.total;
        _state = LoadingState.loaded;
      } else {
        _errorMessage = response.error ?? 'Failed to load drivers';
        _state = LoadingState.error;
      }
    } on UnauthorizedException {
      _errorMessage = 'Session expired. Please login again.';
      _state = LoadingState.error;
      rethrow;
    } catch (e) {
      _errorMessage = 'Error loading drivers: $e';
      _state = LoadingState.error;
    }

    notifyListeners();
  }

  /// Load next page
  Future<void> loadNextPage() async {
    if (!hasMore || _state == LoadingState.loading) return;
    _currentPage++;
    await loadDrivers();
  }

  /// Set search query
  void setSearchQuery(String query) {
    _searchQuery = query;
    loadDrivers(refresh: true);
  }

  /// Set risk level filter
  void setRiskFilter(String filter) {
    _riskFilter = filter;
    loadDrivers(refresh: true);
  }

  /// Toggle registered-only filter
  void toggleRegisteredOnly() {
    _registeredOnly = !_registeredOnly;
    loadDrivers(refresh: true);
  }

  /// Set registered-only filter
  void setRegisteredOnly(bool value) {
    _registeredOnly = value;
    loadDrivers(refresh: true);
  }

  /// Set sorting
  void setSorting(String sortBy, {String order = 'asc'}) {
    _sortBy = sortBy;
    _sortOrder = order;
    loadDrivers(refresh: true);
  }

  /// Load single driver details
  Future<void> loadDriverDetail(String driverId) async {
    _detailState = LoadingState.loading;
    _selectedDriver = null;
    notifyListeners();

    try {
      final response = await _apiClient.get(
        ApiEndpoints.driverDetail(driverId),
      );

      if (response.success && response.data != null) {
        _selectedDriver = Driver.fromJson(response.data!);
        _detailState = LoadingState.loaded;
      } else {
        _errorMessage = response.error ?? 'Failed to load driver details';
        _detailState = LoadingState.error;
      }
    } on UnauthorizedException {
      _errorMessage = 'Session expired. Please login again.';
      _detailState = LoadingState.error;
      rethrow;
    } catch (e) {
      _errorMessage = 'Error loading driver: $e';
      _detailState = LoadingState.error;
    }

    notifyListeners();
  }

  /// Reset search query and filters to defaults
  void resetFilters() {
    _searchQuery = '';
    _riskFilter = 'all';
    _registeredOnly = true;
  }

  /// Clear selected driver
  void clearSelection() {
    _selectedDriver = null;
    _detailState = LoadingState.initial;
    notifyListeners();
  }
}
