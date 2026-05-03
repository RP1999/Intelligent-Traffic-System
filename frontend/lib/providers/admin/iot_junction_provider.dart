import 'dart:async';
import 'package:flutter/foundation.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../models/iot_junction.dart';

enum IotJunctionLoadingState { initial, loading, loaded, error }

/// Provider for IoT junction integration data from backend sync module.
class IotJunctionProvider extends ChangeNotifier {
  final ApiClient _apiClient = ApiClient();

  IotJunctionLoadingState _state = IotJunctionLoadingState.initial;
  IotJunctionStatus? _status;
  String? _errorMessage;
  Timer? _pollTimer;

  IotJunctionLoadingState get state => _state;
  IotJunctionStatus? get status => _status;
  String? get errorMessage => _errorMessage;

  Future<void> loadLatest({bool silent = false, bool forceRefresh = false}) async {
    if (!silent) {
      _state = IotJunctionLoadingState.loading;
      notifyListeners();
    }

    try {
      final response = await _apiClient.get(
        ApiEndpoints.iotJunctionLatest,
        queryParams: forceRefresh ? {'force_refresh': 'true'} : null,
      );

      if (response.success && response.data != null) {
        _status = IotJunctionStatus.fromJson(response.data!);
        _state = IotJunctionLoadingState.loaded;
        _errorMessage = null;
      } else {
        _state = IotJunctionLoadingState.error;
        _errorMessage = response.error ?? 'Failed to load IoT junction status';
      }
    } on UnauthorizedException {
      _state = IotJunctionLoadingState.error;
      _errorMessage = 'Session expired. Please login again.';
      rethrow;
    } catch (e) {
      _state = IotJunctionLoadingState.error;
      _errorMessage = 'Error loading IoT status: $e';
    }

    notifyListeners();
  }

  /// Start lightweight polling for near real-time updates.
  void startPolling({Duration interval = const Duration(seconds: 5)}) {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(interval, (_) {
      loadLatest(silent: true);
    });
  }

  void stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> triggerManualSync() async {
    _state = IotJunctionLoadingState.loading;
    notifyListeners();

    try {
      final response = await _apiClient.post(ApiEndpoints.iotJunctionSync, body: {});
      if (response.success && response.data != null) {
        _status = IotJunctionStatus.fromJson(response.data!);
        _state = IotJunctionLoadingState.loaded;
        _errorMessage = null;
      } else {
        _state = IotJunctionLoadingState.error;
        _errorMessage = response.error ?? 'Failed to run IoT sync';
      }
    } on UnauthorizedException {
      _state = IotJunctionLoadingState.error;
      _errorMessage = 'Session expired. Please login again.';
      rethrow;
    } catch (e) {
      _state = IotJunctionLoadingState.error;
      _errorMessage = 'Error running sync: $e';
    }

    notifyListeners();
  }

  @override
  void dispose() {
    stopPolling();
    super.dispose();
  }
}
