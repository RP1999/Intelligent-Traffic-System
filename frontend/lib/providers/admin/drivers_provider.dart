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
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, dynamic>{
        'limit': _pageSize.toString(),
        'offset': ((_currentPage - 1) * _pageSize).toString(),
        'sort_by': _sortBy,
        'order': _sortOrder,
      };

      final response = await _apiClient.get(
        ApiEndpoints.allDrivers,
        queryParams: queryParams,
      );

      if (response.success && response.data != null) {
        final parsed = DriversResponse.fromJson(response.data!);
        
        // Apply client-side search filtering
        var filtered = parsed.drivers;
        if (_searchQuery.isNotEmpty) {
          final query = _searchQuery.toLowerCase();
          filtered = filtered.where((d) {
            return d.driverId.toLowerCase().contains(query) ||
                (d.phone?.toLowerCase().contains(query) ?? false) ||
                (d.name?.toLowerCase().contains(query) ?? false);
          }).toList();
        }

        if (refresh) {
          _drivers = filtered;
        } else {
          _drivers.addAll(filtered);
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

  /// Clear selected driver
  void clearSelection() {
    _selectedDriver = null;
    _detailState = LoadingState.initial;
    notifyListeners();
  }
}
