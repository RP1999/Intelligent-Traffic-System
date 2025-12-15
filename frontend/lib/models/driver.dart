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
