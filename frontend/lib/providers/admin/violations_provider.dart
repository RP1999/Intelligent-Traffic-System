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
