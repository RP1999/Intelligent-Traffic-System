import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/services/cache_service.dart';
import '../../models/fine.dart';

/// Loading state
enum FinesLoadState { idle, loading, loaded, error }

/// Provider for driver's fines
class DriverFinesProvider with ChangeNotifier {
  final ApiClient _apiClient = ApiClient();
  final CacheService _cache = CacheService();

  FinesLoadState _state = FinesLoadState.idle;
  List<Fine> _fines = [];
  double _totalUnpaid = 0;
  String _currency = 'LKR';
  String _statusFilter = 'all'; // all, unpaid, paid
  String? _error;
  bool _isOffline = false;

  // Payment state
  bool _isProcessingPayment = false;
  String? _paymentError;
  Fine? _lastPaidFine;

  // Getters
  FinesLoadState get state => _state;
  List<Fine> get fines => _filteredFines;
  List<Fine> get allFines => _fines;
  double get totalUnpaid => _totalUnpaid;
  String get currency => _currency;
  String get statusFilter => _statusFilter;
  String? get error => _error;
  bool get isLoading => _state == FinesLoadState.loading;
  bool get isProcessingPayment => _isProcessingPayment;
  String? get paymentError => _paymentError;
  Fine? get lastPaidFine => _lastPaidFine;
  bool get isOffline => _isOffline;

  List<Fine> get _filteredFines {
    if (_statusFilter == 'all') return _fines;
    return _fines.where((f) => f.status.toLowerCase() == _statusFilter).toList();
  }

  double get totalPaid {
    return _fines
        .where((f) => f.isPaid)
        .fold(0.0, (sum, f) => sum + f.amount);
  }

  int get unpaidCount => _fines.where((f) => !f.isPaid).length;
  int get paidCount => _fines.where((f) => f.isPaid).length;

  /// Set status filter
  void setStatusFilter(String filter) {
    _statusFilter = filter;
    notifyListeners();
  }

  /// Load fines
  Future<void> loadFines({bool refresh = false}) async {
    _state = FinesLoadState.loading;
    _error = null;
    _isOffline = false;
    notifyListeners();

    try {
      final response = await _apiClient.get(ApiEndpoints.myFines);

      if (response.success && response.data != null) {
        final data = response.data!;
        final finesResponse = FinesResponse.fromJson(data);
        _fines = finesResponse.fines;
        _totalUnpaid = finesResponse.totalUnpaidAmount;
        _currency = finesResponse.currency;
        _state = FinesLoadState.loaded;
        // Cache fines data
        await _cache.put(CacheService.keyFines, data);
      } else {
        _state = FinesLoadState.error;
        _error = 'Failed to load fines';
      }
    } catch (e) {
      // Offline fallback
      _isOffline = true;
      final cached = await _cache.getStale(CacheService.keyFines);
      if (cached != null) {
        final data = Map<String, dynamic>.from(cached);
        final finesResponse = FinesResponse.fromJson(data);
        _fines = finesResponse.fines;
        _totalUnpaid = finesResponse.totalUnpaidAmount;
        _currency = finesResponse.currency;
        _state = FinesLoadState.loaded;
        _error = 'Showing cached data (offline)';
      } else {
        _state = FinesLoadState.error;
        _error = 'No connection and no cached data';
      }
    }
    notifyListeners();
  }

  /// Process payment via backend API
  Future<bool> processPayment({
    required Fine fine,
    required String paymentMethod,
    required String cardNumber,
  }) async {
    _isProcessingPayment = true;
    _paymentError = null;
    notifyListeners();

    try {
      // Basic validation
      if (cardNumber.length < 16) {
        _paymentError = 'Invalid card number';
        _isProcessingPayment = false;
        notifyListeners();
        return false;
      }

      // Call backend API to process payment
      final response = await _apiClient.post(
        '/driver/fines/${fine.fineId}/pay',
        body: {
          'payment_method': paymentMethod,
        },
      );

      if (response.success) {
        // Update local state
        final idx = _fines.indexWhere((f) => f.fineId == fine.fineId);
        if (idx != -1) {
          _fines[idx] = Fine(
            fineId: fine.fineId,
            violationType: fine.violationType,
            amount: fine.amount,
            issuedDate: fine.issuedDate,
            dueDate: fine.dueDate,
            status: 'paid',
            breakdown: fine.breakdown,
          );
          _totalUnpaid = _fines
              .where((f) => !f.isPaid)
              .fold(0.0, (sum, f) => sum + f.amount);
          _lastPaidFine = _fines[idx];
        }

        _isProcessingPayment = false;
        notifyListeners();
        return true;
      } else {
        _paymentError = response.error ?? 'Payment failed';
        _isProcessingPayment = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _paymentError = e.toString();
      _isProcessingPayment = false;
      notifyListeners();
      return false;
    }
  }

  /// Refresh
  Future<void> refresh() => loadFines(refresh: true);
}
