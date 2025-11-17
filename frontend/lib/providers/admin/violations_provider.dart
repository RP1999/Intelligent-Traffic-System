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
  final int _pageSize = 20;

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

