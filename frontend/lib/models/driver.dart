  /// Driver model representing registered drivers
class Driver {
  final String driverId;
  final int currentScore;
  final int totalViolations;
  final double totalFines;
  final DateTime? lastViolation;
  final String riskLevel;
  final String? phone;
  final String? name;
  final List<DriverViolation>? recentViolations;

  Driver({
    required this.driverId,
    required this.currentScore,
    required this.totalViolations,
    required this.totalFines,
    this.lastViolation,
    required this.riskLevel,
    this.phone,
    this.name,
    this.recentViolations,
  });

  factory Driver.fromJson(Map<String, dynamic> json) {
    return Driver(
      driverId: json['driver_id'] ?? '',
      currentScore: json['current_score'] ?? 100,
      totalViolations: json['total_violations'] ?? 0,
      totalFines: (json['total_fines'] ?? 0).toDouble(),
      lastViolation: json['last_violation'] != null
          ? DateTime.tryParse(json['last_violation'])
          : null,
      riskLevel: json['risk_level'] ?? _getRiskLevel(json['current_score'] ?? 100),
      phone: json['phone'],
      name: json['name'],
      recentViolations: json['recent_violations'] != null
          ? (json['recent_violations'] as List)
              .map((v) => DriverViolation.fromJson(v))
              .toList()
          : null,
    );
  }

  static String _getRiskLevel(int score) {
    if (score >= 90) return 'excellent';
    if (score >= 70) return 'good';
    if (score >= 50) return 'fair';
    if (score >= 30) return 'poor';
    return 'critical';
  }

  Map<String, dynamic> toJson() {
    return {
        'driver_id': driverId,
      'current_score': currentScore,
      'total_violations': totalViolations,
      'total_fines': totalFines,
      'last_violation': lastViolation?.toIso8601String(),
      'risk_level': riskLevel,
      'phone': phone,
      'name': name,
    };
  }

  /// Get display-friendly risk level
  String get displayRiskLevel {
    switch (riskLevel.toLowerCase()) {
      case 'excellent':
        return 'Excellent';
      case 'good':
        return 'Good';
      case 'fair':
        return 'Fair';
      case 'poor':
        return 'Poor';
      case 'critical':
        return 'Critical';
      default:
        return riskLevel;
    }
  }
}

/// Simplified violation for driver history
class DriverViolation {
  final String violationId;
  final String violationType;
  final DateTime timestamp;
  final double fineAmount;

  DriverViolation({
    required this.violationId,
    required this.violationType,
    required this.timestamp,
    required this.fineAmount,
  });

  factory DriverViolation.fromJson(Map<String, dynamic> json) {
    return DriverViolation(
      violationId: json['violation_id'] ?? '',
      violationType: json['violation_type'] ?? 'unknown',
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      fineAmount: (json['fine_amount'] ?? 0).toDouble(),
    );
  }
}

/// Response wrapper for paginated drivers
class DriversResponse {
  final List<Driver> drivers;
  final int total;
  final int limit;
  final int offset;

  DriversResponse({
    required this.drivers,
    required this.total,
    required this.limit,
    required this.offset,
  });

  factory DriversResponse.fromJson(Map<String, dynamic> json) {
    return DriversResponse(
      drivers: ((json['drivers'] ?? []) as List)
          .map((d) => Driver.fromJson(d))
          .toList(),
      total: json['total'] ?? 0,
      limit: json['limit'] ?? 50,
      offset: json['offset'] ?? 0,
    );
  }

  bool get hasMore => offset + drivers.length < total;
  int get currentPage => (offset / limit).floor() + 1;
  int get totalPages => (total / limit).ceil();
}
