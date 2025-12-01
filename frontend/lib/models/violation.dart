/// Violation model representing traffic violations
class Violation {
  final String violationId;
  final String driverId;
  final String? licensePlate;
  final String violationType;
  final DateTime timestamp;
  final String? location;
  final double fineAmount;
  final int pointsDeducted;
  final String? evidencePath;
  final String? snapshotPath;
  final String? notes;
  final String status; // unpaid, paid, disputed, verified, dismissed

  Violation({
    required this.violationId,
    required this.driverId,
    this.licensePlate,
    required this.violationType,
    required this.timestamp,
    this.location,
    required this.fineAmount,
    required this.pointsDeducted,
