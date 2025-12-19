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

  factory ViolationTrendsResponse.fromJson(Map<String, dynamic> json) {
    return ViolationTrendsResponse(
      periodDays: json['period_days'] ?? 7,
      startDate: json['start_date'] ?? '',
      trends: ((json['trends'] ?? []) as List)
          .map((t) => ViolationTrend.fromJson(t))
          .toList(),
    );
  }

  /// Get aggregated violation counts by type
  Map<String, int> get aggregatedByType {
    final result = <String, int>{};
    for (final trend in trends) {
      for (final entry in trend.byType.entries) {
        result[entry.key] = (result[entry.key] ?? 0) + entry.value;
      }
    }
    return result;
  }
}

/// Hotspot location data
class ViolationHotspot {
  final String location;
  final int violationCount;
  final double totalFines;

  ViolationHotspot({
    required this.location,
    required this.violationCount,
    required this.totalFines,
  });

  factory ViolationHotspot.fromJson(Map<String, dynamic> json) {
    return ViolationHotspot(
