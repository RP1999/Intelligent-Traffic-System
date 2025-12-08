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
