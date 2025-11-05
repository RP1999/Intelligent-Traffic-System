import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../models/driver.dart';

/// State enum for data loading
enum LoadingState { initial, loading, loaded, error }

