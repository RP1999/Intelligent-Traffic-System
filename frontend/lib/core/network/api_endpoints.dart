/// API endpoint constants
class ApiEndpoints {
  ApiEndpoints._();

  // ============== AUTH ENDPOINTS ==============
  
  static const String adminLogin = '/auth/admin/login';
  static const String driverLogin = '/auth/driver/login';
  static const String driverRegister = '/auth/driver/register';

  // ============== ADMIN ENDPOINTS ==============
  
  static const String dashboardStats = '/admin/dashboard/stats';
  static const String allViolations = '/admin/violations';
  static String violationDetail(String id) => '/admin/violations/$id';
  static const String allDrivers = '/admin/drivers';
  static String driverDetail(String id) => '/admin/drivers/$id';
  static const String emergencyTrigger = '/admin/emergency/trigger';
  static const String emergencyClear = '/admin/emergency/clear';
  static const String violationTrends = '/admin/analytics/violation-trends';
  static const String violationHotspots = '/admin/analytics/hotspots';
  static const String iotJunctionLatest = '/admin/iot/junction/latest';
  static const String iotJunctionSync = '/admin/iot/junction/sync';
  static const String iotJunctionHistory = '/admin/iot/junction/history';
  
  // Admin config endpoints
  static const String adminZones = '/admin/zones';
  static const String adminLogs = '/admin/logs';
  static const String videoSnapshot = '/admin/video/snapshot';
  static const String videoSnapshotRefresh = '/admin/video/snapshot/refresh';
  static const String adminStats = '/admin/stats';
  static const String stopLineConfig = '/admin/stop-line';

  // ============== SETTINGS ENDPOINTS ==============
  
  static const String systemSettings = '/settings';
  static const String fineSettings = '/settings/fines';
  static const String junctionSafetySettings = '/settings/junction-safety';
  static const String detectionSettings = '/settings/detection';
  static const String parkingSettings = '/settings/parking';
  static const String resetSettings = '/settings/reset';

  // ============== DRIVER ENDPOINTS ==============
  
  static const String driverProfile = '/driver/me';
  static const String myViolations = '/driver/my-violations';
  static const String myFines = '/driver/my-fines';
  static const String myNotifications = '/driver/notifications';
  static String markNotificationRead(int id) => '/driver/notifications/$id/read';
  static const String scoreHistory = '/driver/score-history';
  static const String registerFcmToken = '/driver/fcm-token';

  // ============== COMMUNITY ENDPOINTS ==============
  
  static const String junctionScore = '/community/junction-score';
  static const String allJunctionScores = '/community/junction-scores';
  static const String communityAlerts = '/community/alerts';
  static const String trafficSummary = '/community/traffic-summary';
  static const String violationStats = '/community/violation-stats';
  static const String safetyTips = '/community/safety-tips';

  // ============== SIGNAL ENDPOINTS ==============
  
  static const String signalStatus = '/signal/four-way-status';
  static const String signalHistory = '/signal/timing-history';

  // ============== VIDEO ENDPOINTS ==============
  
  static const String videoStream = '/video/detect-stream';
  static const String videoStatus = '/video/status';
  static const String videoStop = '/video/stop';

  // ============== PARKING ENDPOINTS ==============
  
  static const String parkingStatus = '/parking/status';
  static const String currentViolations = '/parking/current-violations';

  // ============== JUNCTION ENDPOINTS ==============
  
  static const String junctionSafety = '/junction/safety';
  static const String junctionHistory = '/junction/safety-history';

  // ============== RISK PREDICTION ENDPOINTS ==============
  
  static const String riskCurrentScores = '/risk/current-scores';
  static String riskVehicle(String id) => '/risk/vehicle/$id';
  static const String riskHighRiskVehicles = '/risk/high-risk-vehicles';
  static const String riskBehaviorLog = '/risk/behavior-log';
  static const String riskStats = '/risk/stats';
}
