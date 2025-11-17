/// Violation model representing traffic violations
class Violation {
  final String violationId;
  final String driverId;
  final String? licensePlate;
  final String violationType;
  final DateTime timestamp;
  final String? location;
  final double fineAmount;
