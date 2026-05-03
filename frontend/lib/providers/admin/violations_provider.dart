import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../models/violation.dart';

/// State enum for data loading
enum LoadingState { initial, loading, loaded, error }

/// Provider for managing violations data
class ViolationsProvider extends ChangeNotifier {
  final ApiClient _apiClient = ApiClient();

  // State
  LoadingState _state = LoadingState.initial;
  String? _errorMessage;
  List<Violation> _violations = [];
  int _total = 0;
  int _currentPage = 1;
  final int _pageSize = 50;

  // Filters
  String _searchQuery = '';
  String? _statusFilter;
  String? _typeFilter;
  String? _dateFrom;
  String? _dateTo;

  // Selected violation for detail view
  Violation? _selectedViolation;
  LoadingState _detailState = LoadingState.initial;

  // Getters
  LoadingState get state => _state;
  String? get errorMessage => _errorMessage;
  List<Violation> get violations => _violations;
  int get total => _total;
  int get currentPage => _currentPage;
  int get totalPages => (_total / _pageSize).ceil();
  bool get hasMore => _violations.length < _total;
  String get searchQuery => _searchQuery;
  String? get statusFilter => _statusFilter;
  String? get typeFilter => _typeFilter;
  String? get dateFrom => _dateFrom;
  String? get dateTo => _dateTo;
  Violation? get selectedViolation => _selectedViolation;
  LoadingState get detailState => _detailState;

  /// Load violations with current filters
  Future<void> loadViolations({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 1;
      _violations = [];
    }

    _state = _violations.isEmpty ? LoadingState.loading : _state;
    _errorMessage = null;
    notifyListeners();

    try {
      final queryParams = <String, dynamic>{
        'limit': _pageSize.toString(),
        'offset': ((_currentPage - 1) * _pageSize).toString(),
      };

      if (_typeFilter != null && _typeFilter!.isNotEmpty) {
        queryParams['violation_type'] = _typeFilter!;
      }
      if (_statusFilter != null && _statusFilter!.isNotEmpty) {
        queryParams['status'] = _statusFilter!;
      }
      if (_dateFrom != null) {
        queryParams['date_from'] = _dateFrom!;
      }
      if (_dateTo != null) {
        queryParams['date_to'] = _dateTo!;
      }

      final response = await _apiClient.get(
        ApiEndpoints.allViolations,
        queryParams: queryParams,
      );

      if (response.success && response.data != null) {
        final parsed = ViolationsResponse.fromJson(response.data!);
        
        // Apply client-side search filtering
        var filtered = parsed.violations;
        if (_searchQuery.isNotEmpty) {
          final query = _searchQuery.toLowerCase();
          filtered = filtered.where((v) {
            return (v.licensePlate?.toLowerCase().contains(query) ?? false) ||
                v.violationId.toLowerCase().contains(query) ||
                v.driverId.toLowerCase().contains(query);
          }).toList();
        }

        // Status is now filtered server-side

        if (refresh) {
          _violations = filtered;
        } else {
          _violations.addAll(filtered);
        }
        _total = parsed.total;
        _state = LoadingState.loaded;
      } else {
        _errorMessage = response.error ?? 'Failed to load violations';
        _state = LoadingState.error;
      }
    } on UnauthorizedException {
      _errorMessage = 'Session expired. Please login again.';
      _state = LoadingState.error;
      rethrow;
    } catch (e) {
      _errorMessage = 'Error loading violations: $e';
      _state = LoadingState.error;
    }

    notifyListeners();
  }

  /// Load next page
  Future<void> loadNextPage() async {
    if (!hasMore || _state == LoadingState.loading) return;
    _currentPage++;
    await loadViolations();
  }

  /// Go to a specific page (replaces current list)
  Future<void> goToPage(int page) async {
    if (page < 1 || _state == LoadingState.loading) return;
    _currentPage = page;
    await loadViolations(refresh: true);
  }

  /// Set search query and reload
  void setSearchQuery(String query) {
    _searchQuery = query;
    loadViolations(refresh: true);
  }

  /// Set status filter
  void setStatusFilter(String? status) {
    _statusFilter = status;
    loadViolations(refresh: true);
  }

  /// Set type filter
  void setTypeFilter(String? type) {
    _typeFilter = type;
    loadViolations(refresh: true);
  }

  /// Set date range filter
  void setDateRange(String? from, String? to) {
    _dateFrom = from;
    _dateTo = to;
    loadViolations(refresh: true);
  }

  /// Clear all filters
  void clearFilters() {
    _searchQuery = '';
    _statusFilter = null;
    _typeFilter = null;
    _dateFrom = null;
    _dateTo = null;
    loadViolations(refresh: true);
  }

  /// Load single violation details
  Future<void> loadViolationDetail(String violationId) async {
    _detailState = LoadingState.loading;
    _selectedViolation = null;
    notifyListeners();

    try {
      final response = await _apiClient.get(
        ApiEndpoints.violationDetail(violationId),
      );

      if (response.success && response.data != null) {
        _selectedViolation = Violation.fromJson(response.data!);
        _detailState = LoadingState.loaded;
      } else {
        _errorMessage = response.error ?? 'Failed to load violation details';
        _detailState = LoadingState.error;
      }
    } on UnauthorizedException {
      _errorMessage = 'Session expired. Please login again.';
      _detailState = LoadingState.error;
      rethrow;
    } catch (e) {
      _errorMessage = 'Error loading violation: $e';
      _detailState = LoadingState.error;
    }

    notifyListeners();
  }

  /// Delete a violation (dismiss)
  Future<bool> deleteViolation(String violationId) async {
    try {
      final response = await _apiClient.delete(
        ApiEndpoints.violationDetail(violationId),
      );

      if (response.success) {
        _violations.removeWhere((v) => v.violationId == violationId);
        _total = (_total - 1).clamp(0, _total);
        notifyListeners();
        return true;
      }
      return false;
    } catch (e) {
      _errorMessage = 'Failed to delete violation: $e';
      notifyListeners();
      return false;
    }
  }

  /// Update violation status (verify/dismiss/paid)
  Future<bool> updateViolationStatus(String violationId, String newStatus) async {
    try {
      final response = await _apiClient.patch(
        '${ApiEndpoints.violationDetail(violationId)}/status?new_status=$newStatus',
      );

      if (response.success) {
        // Update locally
        final index = _violations.indexWhere((v) => v.violationId == violationId);
        if (index != -1) {
          // Create updated violation with new status
          final old = _violations[index];
          _violations[index] = Violation(
            violationId: old.violationId,
            driverId: old.driverId,
            violationType: old.violationType,
            licensePlate: old.licensePlate,
            timestamp: old.timestamp,
            location: old.location,
            status: newStatus,
            fineAmount: old.fineAmount,
            pointsDeducted: old.pointsDeducted,
            evidencePath: old.evidencePath,
            snapshotPath: old.snapshotPath,
            notes: old.notes,
          );
        }
        notifyListeners();
        return true;
      }
      return false;
    } catch (e) {
      _errorMessage = 'Failed to update violation status: $e';
      notifyListeners();
      return false;
    }
  }

  /// Clear selected violation
  void clearSelection() {
    _selectedViolation = null;
    _detailState = LoadingState.initial;
    notifyListeners();
  }
}
