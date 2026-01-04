/// App configuration constants
class AppConfig {
  AppConfig._();

  // ============== API CONFIGURATION ==============
  
  /// Base URL for the FastAPI backend (data APIs)
  /// Using localhost to match the frontend origin for CORS
  static const String apiBaseUrl = 'http://localhost:8000';
  
  /// Base URL for video-related endpoints
  /// Uses 'localhost' instead of '127.0.0.1' to bypass browser's 6-connection limit
  /// Browser treats localhost and 127.0.0.1 as different origins = separate connection pools
  static const String videoBaseUrl = 'http://localhost:8000';
  
  /// Video stream endpoint (MJPEG stream with detection overlay)
  static const String videoStreamUrl = '$videoBaseUrl/video/stream';
  
  /// API timeout duration
  static const Duration apiTimeout = Duration(seconds: 30);
  
  /// Token refresh threshold (refresh if less than this remaining)
  static const Duration tokenRefreshThreshold = Duration(hours: 1);

  // ============== APP INFO ==============
  
  /// App name
  static const String appName = 'Traffic Control Center';
  
  /// App version
  static const String appVersion = '1.0.0';
  
  /// Copyright text
  static const String copyright = '© 2025 Intelligent Traffic Management System';

  // ============== STORAGE KEYS ==============
  
  /// JWT token storage key
  static const String tokenKey = 'jwt_token';
  
  /// User type storage key (admin/driver)
  static const String userTypeKey = 'user_type';
  
  /// User data storage key
  static const String userDataKey = 'user_data';
  
  /// Remember me preference
  static const String rememberMeKey = 'remember_me';

  // ============== UI CONFIGURATION ==============
  
  /// Sidebar width (desktop)
  static const double sidebarWidth = 260;
  
  /// Sidebar collapsed width
  static const double sidebarCollapsedWidth = 80;
  
  /// Card border radius
  static const double cardRadius = 16;
  
  /// Button border radius
  static const double buttonRadius = 12;
  
  /// Input border radius
  static const double inputRadius = 12;
  
  /// Default padding
  static const double paddingSmall = 8;
  static const double paddingMedium = 16;
  static const double paddingLarge = 24;
  static const double paddingXLarge = 32;

  // ============== BREAKPOINTS ==============
  
  /// Mobile breakpoint
  static const double mobileBreakpoint = 600;
  
  /// Tablet breakpoint
  static const double tabletBreakpoint = 900;
  
  /// Desktop breakpoint
  static const double desktopBreakpoint = 1200;

  // ============== ANIMATION DURATIONS ==============
  
  /// Fast animation
  static const Duration animationFast = Duration(milliseconds: 150);
  
  /// Normal animation
  static const Duration animationNormal = Duration(milliseconds: 300);
  
  /// Slow animation
  static const Duration animationSlow = Duration(milliseconds: 500);

  // ============== REFRESH INTERVALS ==============
  
  /// Dashboard stats refresh interval
  static const Duration dashboardRefreshInterval = Duration(seconds: 10);
  
  /// Signal status refresh interval
  static const Duration signalRefreshInterval = Duration(seconds: 1);
  
  /// Junction score refresh interval
  static const Duration junctionRefreshInterval = Duration(seconds: 5);
}
