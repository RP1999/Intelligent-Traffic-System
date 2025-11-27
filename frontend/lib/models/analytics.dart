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
    required this.averageRiskScore,
    required this.currentTrafficLevel,
    required this.activeJunctions,
    required this.totalVehiclesToday,
    required this.pendingFines,
    required this.emergencyMode,
  });

  factory DashboardStats.fromJson(Map<String, dynamic> json) {
    return DashboardStats(
      violationsToday: json['violations_today'] ?? 0,
      violationsThisWeek: json['violations_this_week'] ?? 0,
      averageRiskScore: (json['average_risk_score'] ?? 0).toDouble(),
      currentTrafficLevel: json['current_traffic_level'] ?? 'normal',
      activeJunctions: json['active_junctions'] ?? 0,
      totalVehiclesToday: json['total_vehicles_today'] ?? 0,
      pendingFines: (json['pending_fines'] ?? 0).toDouble(),
      emergencyMode: json['emergency_mode'] ?? false,
    );
  }
}

/// Violation trend data for charts
class ViolationTrend {
  final String date;
  final int total;
  final Map<String, int> byType;

  ViolationTrend({
    required this.date,
    required this.total,
    required this.byType,
  });

  factory ViolationTrend.fromJson(Map<String, dynamic> json) {
    final byTypeRaw = json['by_type'] as Map<String, dynamic>? ?? {};
    return ViolationTrend(
      date: json['date'] ?? '',
      total: json['total'] ?? 0,
      byType: byTypeRaw.map((k, v) => MapEntry(k, (v as num).toInt())),
    );
  }
}

/// Violation trends response
class ViolationTrendsResponse {
  final int periodDays;
  final String startDate;
  final List<ViolationTrend> trends;

  ViolationTrendsResponse({
    required this.periodDays,
    required this.startDate,
    required this.trends,
  });

