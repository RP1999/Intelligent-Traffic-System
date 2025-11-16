class Violation {
  final String violationId;
  final String driverId;
  final String? licensePlate;
  final String violationType;
  final double fineAmount;
  final int pointsDeducted;
  final DateTime timestamp;
  final String status;
  final String? location;
  final String? snapshotPath;
  final String? evidencePath;
  final String? notes;

  Violation({
    required this.violationId,
    required this.driverId,
    this.licensePlate,
    required this.violationType,
    required this.fineAmount,
    required this.pointsDeducted,
    required this.timestamp,
    required this.status,
    this.location,
    this.snapshotPath,
    this.evidencePath,
    this.notes,
  });

  factory Violation.fromJson(Map<String, dynamic> json) {
    return Violation(
      violationId: json['violation_id'] ?? '',
