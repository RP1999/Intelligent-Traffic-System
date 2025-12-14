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
    this.evidencePath,
    this.snapshotPath,
    this.notes,
    this.status = 'unpaid',
  });

  factory Violation.fromJson(Map<String, dynamic> json) {
    return Violation(
      violationId: json['violation_id'] ?? '',
      driverId: json['driver_id'] ?? '',
      licensePlate: json['license_plate'],
      violationType: json['violation_type'] ?? 'unknown',
      timestamp: DateTime.tryParse(json['timestamp'] ?? '') ?? DateTime.now(),
      location: json['location'],
      fineAmount: (json['fine_amount'] ?? 0).toDouble(),
