import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/app_config.dart';

/// Exception thrown when user is not authorized (401)
/// UI should catch this and redirect to login
class UnauthorizedException implements Exception {
  final String message;
  UnauthorizedException([this.message = 'Unauthorized - please login again']);
  
  @override
  String toString() => message;
}

/// API Response wrapper
class ApiResponse<T> {
  final bool success;
  final T? data;
  final String? error;
  final int statusCode;

  ApiResponse({
    required this.success,
    this.data,
    this.error,
    required this.statusCode,
  });

  factory ApiResponse.success(T data, int statusCode) {
    return ApiResponse(
      success: true,
      data: data,
      statusCode: statusCode,
    );
  }

  factory ApiResponse.error(String message, int statusCode) {
    return ApiResponse(
      success: false,
      error: message,
      statusCode: statusCode,
    );
  }
}

/// HTTP API Client with JWT authentication support
class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal();

  final String baseUrl = AppConfig.apiBaseUrl;
  String? _token;

  /// Get stored token
  Future<String?> get token async {
    if (_token != null) return _token;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(AppConfig.tokenKey);
    return _token;
  }

  /// Set and store token
  Future<void> setToken(String? token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    if (token != null) {
      await prefs.setString(AppConfig.tokenKey, token);
    } else {
      await prefs.remove(AppConfig.tokenKey);
    }
  }

  /// Clear token (logout)
  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConfig.tokenKey);
    await prefs.remove(AppConfig.userTypeKey);
    await prefs.remove(AppConfig.userDataKey);
  }

  /// Build headers with optional auth
  Future<Map<String, String>> _headers({bool requiresAuth = true}) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (requiresAuth) {
      final authToken = await token;
      if (authToken != null) {
        headers['Authorization'] = 'Bearer $authToken';
      }
    }

    return headers;
  }

  /// GET request
  Future<ApiResponse<Map<String, dynamic>>> get(
    String endpoint, {
    Map<String, dynamic>? queryParams,
    bool requiresAuth = true,
  }) async {
    try {
      var uri = Uri.parse('$baseUrl$endpoint');
      if (queryParams != null) {
        uri = uri.replace(queryParameters: queryParams.map(
          (key, value) => MapEntry(key, value.toString()),
        ));
      }

      final response = await http
          .get(uri, headers: await _headers(requiresAuth: requiresAuth))
          .timeout(AppConfig.apiTimeout);

      return _handleResponse(response);
    } catch (e) {
      return ApiResponse.error(_handleError(e), 0);
    }
  }

  /// POST request
  Future<ApiResponse<Map<String, dynamic>>> post(
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? queryParams,
    bool requiresAuth = true,
  }) async {
    try {
      var uri = Uri.parse('$baseUrl$endpoint');
      if (queryParams != null) {
        uri = uri.replace(queryParameters: queryParams.map(
          (key, value) => MapEntry(key, value.toString()),
        ));
      }

      final response = await http
          .post(
            uri,
            headers: await _headers(requiresAuth: requiresAuth),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(AppConfig.apiTimeout);

      return _handleResponse(response);
    } catch (e) {
      return ApiResponse.error(_handleError(e), 0);
    }
  }

  /// PUT request
  Future<ApiResponse<Map<String, dynamic>>> put(
    String endpoint, {
    Map<String, dynamic>? body,
    bool requiresAuth = true,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl$endpoint');

      final response = await http
          .put(
            uri,
            headers: await _headers(requiresAuth: requiresAuth),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(AppConfig.apiTimeout);

      return _handleResponse(response);
    } catch (e) {
      return ApiResponse.error(_handleError(e), 0);
    }
  }

  /// DELETE request
  Future<ApiResponse<Map<String, dynamic>>> delete(
    String endpoint, {
    Map<String, dynamic>? queryParams,
    bool requiresAuth = true,
  }) async {
    try {
      var uri = Uri.parse('$baseUrl$endpoint');
      if (queryParams != null) {
        uri = uri.replace(queryParameters: queryParams.map(
          (key, value) => MapEntry(key, value.toString()),
        ));
      }

      final response = await http
          .delete(uri, headers: await _headers(requiresAuth: requiresAuth))
          .timeout(AppConfig.apiTimeout);

      return _handleResponse(response);
    } catch (e) {
      return ApiResponse.error(_handleError(e), 0);
    }
  }

  /// Handle HTTP response
  /// Throws UnauthorizedException on 401 to force redirect to login
  ApiResponse<Map<String, dynamic>> _handleResponse(http.Response response) {
    final statusCode = response.statusCode;
    
    // CRITICAL: Throw exception on 401 to force login redirect
    if (statusCode == 401) {
      throw UnauthorizedException('Session expired - please login again');
    }
    
    try {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      
      if (statusCode >= 200 && statusCode < 300) {
        return ApiResponse.success(data, statusCode);
      } else {
        final error = data['detail'] ?? data['message'] ?? 'Request failed';
        return ApiResponse.error(error.toString(), statusCode);
      }
    } catch (e) {
      // Re-throw UnauthorizedException if it was thrown above
      if (e is UnauthorizedException) rethrow;
      
      if (statusCode >= 200 && statusCode < 300) {
        return ApiResponse.success({}, statusCode);
      }
      return ApiResponse.error('Failed to parse response', statusCode);
    }
  }

  /// Handle errors
  String _handleError(dynamic error) {
    if (error.toString().contains('SocketException')) {
      return 'Unable to connect to server. Please check your connection.';
    } else if (error.toString().contains('TimeoutException')) {
      return 'Request timed out. Please try again.';
    } else if (error.toString().contains('FormatException')) {
      return 'Invalid response format from server.';
    }
    return 'An unexpected error occurred: ${error.toString()}';
  }

  /// Check if user is logged in
  Future<bool> isLoggedIn() async {
    final authToken = await token;
    return authToken != null && authToken.isNotEmpty;
  }

  /// Get stored user type
  Future<String?> getUserType() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.userTypeKey);
  }

  /// Set user type
  Future<void> setUserType(String userType) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.userTypeKey, userType);
  }

  /// Get stored user data
  Future<Map<String, dynamic>?> getUserData() async {
    final prefs = await SharedPreferences.getInstance();
    final userData = prefs.getString(AppConfig.userDataKey);
    if (userData != null) {
      return jsonDecode(userData) as Map<String, dynamic>;
    }
    return null;
  }

  /// Set user data
  Future<void> setUserData(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.userDataKey, jsonEncode(data));
  }
}
