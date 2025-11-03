/// Dashboard statistics model
class DashboardStats {
  final int violationsToday;
  final int violationsThisWeek;
  final double averageRiskScore;
  final String currentTrafficLevel;
  final int activeJunctions;
  final int totalVehiclesToday;
  final double pendingFines;
  final bool emergencyMode;

  DashboardStats({
    required this.violationsToday,
    required this.violationsThisWeek,
