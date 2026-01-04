import 'package:flutter/foundation.dart';
import '../core/network/api_client.dart';
import '../core/network/api_endpoints.dart';

// Re-export UnauthorizedException for convenience
export '../core/network/api_client.dart' show UnauthorizedException;

/// User types
enum UserType { admin, driver, none }

/// Authentication state
enum AuthState { initial, loading, authenticated, unauthenticated, error }

/// User model
class User {
  final int id;
  final String phone;
  final String? name;
  final String? plateNumber;
  final UserType userType;

  User({
    required this.id,
    required this.phone,
    this.name,
    this.plateNumber,
    required this.userType,
  });

  factory User.fromJson(Map<String, dynamic> json, UserType type) {
    return User(
      id: json['user_id'] ?? json['id'] ?? 0,
      phone: json['phone'] ?? json['username'] ?? '',
      name: json['name'],
      plateNumber: json['plate_number'],
      userType: type,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'phone': phone,
      'name': name,
      'plate_number': plateNumber,
      'user_type': userType.name,
    };
  }
}

/// Authentication Provider
class AuthProvider with ChangeNotifier {
  final ApiClient _apiClient = ApiClient();

  AuthState _state = AuthState.initial;
  User? _user;
  String? _error;
  String? _token;

  // Getters
  AuthState get state => _state;
  User? get user => _user;
  String? get error => _error;
  String? get token => _token;
  bool get isAuthenticated => _state == AuthState.authenticated;
  bool get isLoading => _state == AuthState.loading;
  bool get isAdmin => _user?.userType == UserType.admin;
  bool get isDriver => _user?.userType == UserType.driver;
  String? get userType => _user?.userType == UserType.admin ? 'admin' : (_user?.userType == UserType.driver ? 'driver' : null);

  /// Initialize auth state from stored token
  /// Validates the token with backend /auth/me endpoint
  /// Throws UnauthorizedException if token is invalid (caught internally)
  Future<void> initialize() async {
    _state = AuthState.loading;
    notifyListeners();

    try {
      final storedToken = await _apiClient.token;
      if (storedToken != null && storedToken.isNotEmpty) {
        _token = storedToken;
        
        // CRITICAL: Validate token with backend before auto-login
        // This will throw UnauthorizedException if token is invalid (401)
        final validateResponse = await _apiClient.get('/auth/me');
        
        if (!validateResponse.success) {
          // Token validation failed - force logout
          print('[AUTH] Token validation failed - clearing stale token');
          await _apiClient.clearToken();
          _token = null;
          _user = null;
          _state = AuthState.unauthenticated;
          notifyListeners();
          return;
        }
        
        // Token is valid - get user info from response or stored data
        final userTypeStr = await _apiClient.getUserType();
        final userData = await _apiClient.getUserData();
        
        if (userTypeStr != null && userData != null) {
          final userType = userTypeStr == 'admin' ? UserType.admin : UserType.driver;
          _user = User.fromJson(userData, userType);
          _state = AuthState.authenticated;
          print('[AUTH] Token validated - user authenticated as $userTypeStr');
        } else {
          // Token valid but no user data stored, try to get from validation response
          if (validateResponse.data != null) {
            final respData = validateResponse.data!;
            final respUserType = respData['user_type'] == 'admin' ? UserType.admin : UserType.driver;
            _user = User(
              id: respData['user_id'] ?? 0,
              phone: respData['identifier'] ?? '',
              userType: respUserType,
            );
            _state = AuthState.authenticated;
          } else {
            // Can't restore user data - clear and require login
            await _apiClient.clearToken();
            _state = AuthState.unauthenticated;
          }
        }
      } else {
        _state = AuthState.unauthenticated;
      }
    } on UnauthorizedException {
      // 401 received - token is invalid, force logout
      print('[AUTH] UnauthorizedException - token invalid, clearing');
      await _apiClient.clearToken();
      _token = null;
      _user = null;
      _state = AuthState.unauthenticated;
    } catch (e) {
      // Network error or other issue - clear token and require login
      print('[AUTH] Initialize error: $e - clearing token');
      await _apiClient.clearToken();
      _token = null;
      _user = null;
      _state = AuthState.unauthenticated;
      _error = e.toString();
    }

    notifyListeners();
  }

  /// Admin login
  Future<bool> adminLogin(String username, String password) async {
    _state = AuthState.loading;
    _error = null;
    notifyListeners();

    try {
      final response = await _apiClient.post(
        ApiEndpoints.adminLogin,
        body: {
          'username': username,
          'password': password,
        },
        requiresAuth: false,
      );

      if (response.success && response.data != null) {
        _token = response.data!['access_token'];
        await _apiClient.setToken(_token);
        await _apiClient.setUserType('admin');
        
        // Create admin user from response
        _user = User(
          id: response.data!['user_id'] ?? 0,
          phone: username,
          name: 'Administrator',
          userType: UserType.admin,
        );
        
        await _apiClient.setUserData(_user!.toJson());
        
        _state = AuthState.authenticated;
        notifyListeners();
        return true;
      } else {
        _error = response.error ?? 'Login failed';
        _state = AuthState.error;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _state = AuthState.error;
      notifyListeners();
      return false;
    }
  }

  /// Driver login
  Future<bool> driverLogin(String phone, String password) async {
    _state = AuthState.loading;
    _error = null;
    notifyListeners();

    try {
      final response = await _apiClient.post(
        ApiEndpoints.driverLogin,
        body: {
          'phone': phone,
          'password': password,
        },
        requiresAuth: false,
      );

      if (response.success && response.data != null) {
        _token = response.data!['access_token'];
        await _apiClient.setToken(_token);
        await _apiClient.setUserType('driver');
        
        // Create driver user from response
        _user = User(
          id: response.data!['user_id'] ?? 0,
          phone: phone,
          name: response.data!['name'],
          plateNumber: response.data!['plate_number'],
          userType: UserType.driver,
        );
        
        await _apiClient.setUserData(_user!.toJson());
        
        _state = AuthState.authenticated;
        notifyListeners();
        return true;
      } else {
        _error = response.error ?? 'Login failed';
        _state = AuthState.error;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _state = AuthState.error;
      notifyListeners();
      return false;
    }
  }

  /// Driver registration
  Future<bool> driverRegister({
    required String phone,
    required String password,
    required String plateNumber,
    String? name,
    String? licenseNumber,
  }) async {
    _state = AuthState.loading;
    _error = null;
    notifyListeners();

    // Frontend validation
    if (phone.length < 10) {
      _error = 'Phone number must be at least 10 characters';
      _state = AuthState.error;
      notifyListeners();
      return false;
    }
    
    if (password.length < 6) {
      _error = 'Password must be at least 6 characters';
      _state = AuthState.error;
      notifyListeners();
      return false;
    }
    
    if (plateNumber.isEmpty) {
      _error = 'License plate number is required';
      _state = AuthState.error;
      notifyListeners();
      return false;
    }

    try {
      final response = await _apiClient.post(
        ApiEndpoints.driverRegister,
        body: {
          'phone': phone,
          'password': password,
          'plate_number': plateNumber,
          if (name != null) 'name': name,
          if (licenseNumber != null) 'license_number': licenseNumber,
        },
        requiresAuth: false,
      );

      if (response.success && response.data != null) {
        // Auto-login after registration
        _token = response.data!['access_token'];
        await _apiClient.setToken(_token);
        await _apiClient.setUserType('driver');
        
        _user = User(
          id: response.data!['user_id'] ?? 0,
          phone: phone,
          name: name,
          plateNumber: plateNumber,
          userType: UserType.driver,
        );
        
        await _apiClient.setUserData(_user!.toJson());
        
        _state = AuthState.authenticated;
        notifyListeners();
        return true;
      } else {
        _error = response.error ?? 'Registration failed';
        _state = AuthState.error;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _error = e.toString();
      _state = AuthState.error;
      notifyListeners();
      return false;
    }
  }

  /// Logout - stops video stream and clears auth
  Future<void> logout() async {
    // Stop the backend video stream and TTS before clearing auth
    // Use a timeout to prevent hanging if backend is unresponsive
    try {
      await _apiClient.post(ApiEndpoints.videoStop).timeout(
        const Duration(seconds: 2),
        onTimeout: () {
          // Return empty response on timeout - don't block logout
          return ApiResponse(success: true, data: null, statusCode: 200);
        },
      );
    } catch (e) {
      // Ignore errors - stream might not be running
    }
    
    // Clear auth state immediately - don't wait for backend
    await _apiClient.clearToken();
    _token = null;
    _user = null;
    _state = AuthState.unauthenticated;
    _error = null;
    notifyListeners();
  }

  /// Clear error
  void clearError() {
    _error = null;
    if (_state == AuthState.error) {
      _state = AuthState.unauthenticated;
    }
    notifyListeners();
  }
}
